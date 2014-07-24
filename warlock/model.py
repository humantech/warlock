# Copyright 2012 Brian Waldon
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Self-validating model for arbitrary objects"""

import copy
import warnings

import jsonpatch
import jsonschema
import six

from . import exceptions

Classes = None


class Model(dict):
    def __init__(self, *args, **kwargs):
        # we overload setattr so set this manually
        d = dict(*args, **kwargs)

        # try:
        #     self.validate(d)
        # except exceptions.ValidationError as exc:
        #     raise ValueError(str(exc))
        # else:
        #     dict.__init__(self, d)

        self._set_defaults(self.schema, d)
        dict.__init__(self, d)
        self.__dict__['changes'] = {}
        self.__dict__['__original__'] = copy.deepcopy(d)

    def _set_defaults(self, schema, values):
        props = schema.get('properties', {})
        if Classes is not None and schema is not self.schema:
            base_class = Classes.get(schema.get('name'))
            if base_class is not None:
                return base_class(values)
        else:
            for k, v in props.items():
                if 'properties' in v:
                    new_value = self._set_defaults(v, values.get(k))
                    if new_value is not None:
                        values[k] = new_value
                if v.get('type') == 'array':
                    for i, item in enumerate(values.get(k, [])):
                        new_value = self._set_defaults(v.get('items'), item)
                        if new_value is not None:
                            values.get(k, [])[i] = new_value
                if k not in values and 'default' in v:
                    values[k] = copy.deepcopy(v.get('default'))

    def __setitem__(self, key, value):
        #TODO validation must be lazy to be able to use sub-schemas
        # mutation = dict(self.items())
        # mutation[key] = value
        # try:
        #     self.validate(mutation)
        # except exceptions.ValidationError as exc:
        #     msg = ("Unable to set '%s' to '%s'. Reason: %s"
        #            % (key, value, str(exc)))
        #     raise exceptions.InvalidOperation(msg)

        dict.__setitem__(self, key, value)

        self.__dict__['changes'][key] = value

    def __delitem__(self, key):
        mutation = dict(self.items())
        del mutation[key]
        try:
            self.validate(mutation)
        except exceptions.ValidationError as exc:
            msg = ("Unable to delete attribute '%s'. Reason: %s"
                   % (key, str(exc)))
            raise exceptions.InvalidOperation(msg)

        dict.__delitem__(self, key)

    def __getattr__(self, key):
        try:
            return self.__getitem__(key)
        except KeyError:
            raise AttributeError(key)

    def __setattr__(self, key, value):
        self.__setitem__(key, value)

    def __delattr__(self, key):
        self.__delitem__(key)

    ### BEGIN dict compatibility methods ###

    def clear(self):
        raise exceptions.InvalidOperation()

    def pop(self, key, default=None):
        raise exceptions.InvalidOperation()

    def popitem(self):
        raise exceptions.InvalidOperation()

    def copy(self):
        return copy.deepcopy(dict(self))

    def update(self, other):
        mutation = dict(self.items())
        mutation.update(other)
        try:
            self.validate(mutation)
        except exceptions.ValidationError as exc:
            raise exceptions.InvalidOperation(str(exc))
        dict.update(self, other)

    def iteritems(self):
        return six.iteritems(copy.deepcopy(dict(self)))

    def items(self):
        return copy.deepcopy(dict(self)).items()

    def itervalues(self):
        return six.itervalues(copy.deepcopy(dict(self)))

    def values(self):
        return copy.deepcopy(dict(self)).values()

    ### END dict compatibility methods ###

    @property
    def patch(self):
        """Return a jsonpatch object representing the delta"""
        original = self.__dict__['__original__']
        return jsonpatch.make_patch(original, dict(self)).to_string()

    @property
    def changes(self):
        """Dumber version of 'patch' method"""
        deprecation_msg = 'Model.changes will be removed in warlock v2'
        warnings.warn(deprecation_msg, DeprecationWarning, stacklevel=2)
        return copy.deepcopy(self.__dict__['changes'])

    def validate(self, obj=None):
        """Apply a JSON schema to an object"""
        try:
            if obj is None:
                jsonschema.validate(self, self.schema)
            else:
                jsonschema.validate(obj, self.schema)
        except jsonschema.ValidationError as exc:
            raise exceptions.ValidationError(str(exc))
