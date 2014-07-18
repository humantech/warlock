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

"""Core Warlock functionality"""

import copy

from . import model


def model_factory(schema, base_class=model.Model, parent_class_only=True):
    factory = ModelFactory(schema, base_class)
    if parent_class_only:
        factory.model_registry.get(factory.name)
    else:
        return factory.model_registry


def _model_factory(schema, base_class=model.Model):
    """Generate a model class based on the provided JSON Schema

    :param schema: dict representing valid JSON schema
    """
    schema = copy.deepcopy(schema)

    class NewModel(base_class):
        def __init__(self, *args, **kwargs):
            self.__dict__['schema'] = schema
            base_class.__init__(self, *args, **kwargs)

    NewModel.__name__ = str(schema['name'])
    return NewModel


def get_schema_name(schema):
    identifiers = ['name', 'title', 'id']
    name = None
    for iden in identifiers:
        name = schema.get(iden)
        if name is not None and isinstance(name, (str, unicode)):
            break
        else:
            name = None
    return name


def process_uri(uri):
    if uri is None:
        raise ValueError('uri must not be None')

    sp_uri = uri.split('#')
    file_name = sp_uri[0]
    if len(sp_uri) > 1:
        path = filter(None, sp_uri[1].split('/'))
    else:
        path = []
    return file_name, path


def merge_dict(a, b):
    if a is None or not isinstance(a, dict):
        return b

    for k, v in b.items():
        if isinstance(v, dict):
            a[k] = merge_dict(a.get(k), v)
        elif isinstance(v, list):
            if k in a:
                a[k] += v
            else:
                a.update({k: v})
        else:
            a.update({k: v})

    return a


class ModelFactory(object):
    def __init__(self, schema, base_class=model.Model):
        if not isinstance(schema, dict):
            raise TypeError('expected a dict')
        self.model_registry = dict()
        self.schema = copy.deepcopy(schema)
        self.base_class = base_class
        self.name = get_schema_name(schema)
        self.process_objects(self.schema)

    def process_objects(self, schema):
        schema_name = get_schema_name(schema)

        if schema_name is None and schema.get('type') == 'object':
            raise KeyError('object must have name attribute. "{0}"'.format(schema))

        if schema is not None and schema_name not in self.model_registry:
            for k, v in schema.items():
                if isinstance(v, dict):
                    self.process_objects(v)

            schema_type = schema.get('type')
            if schema_type == 'object':
                new_model = _model_factory(schema, self.base_class)
            elif schema_type == 'array':
                items = schema.get('items')
                if items is None:
                    raise KeyError('array object has no key "items". "{0}"'.format(schema))
                new_model = self.process_objects(items)
            elif '$ref' in schema:
                referenced_key, referenced = self.resolve_reference(schema)
                schema.update(referenced)
                schema.pop('$ref')
                new_model = self.process_objects(referenced)
            elif 'allOf' in schema:
                all_of = self.resolve_all_of(schema)
                new_model = self.process_objects(all_of)
            else:
                new_model = None

            if new_model is not None:
                self.model_registry.update({new_model.__name__: new_model})

            return new_model
        else:
            return self.model_registry.get(schema_name)

    def resolve_reference(self, d):
        if not isinstance(d, dict):
            raise TypeError('expected a dict')

        uri = d.get('$ref')
        file_name, path = process_uri(uri)
        if len(file_name) > 0:
            #TODO process references to load external files (ie.: somefile.json#/definitions/somekey)
            raise NotImplementedError('does not support external files ont $ref URI')

        referenced = self.schema
        referenced_key = None
        for k in path:
            referenced = referenced.get(k)
            referenced_key = k
            if referenced is None:
                raise KeyError('Unable to find referece {0}. Stopped at {1}'.format(uri, k))

        return referenced_key, referenced

    def resolve_all_of(self, all_of_schema):
        origin = list()
        items = list()
        all_of = all_of_schema.get('allOf')
        for i in all_of:
            if not isinstance(i, dict):
                raise ValueError('list "all_of" must contain only dicts. "{0}"'.format(all_of))
            if '$ref' in i:
                rk, r = self.resolve_reference(i)
                i.update(r)
                i.pop('$ref')
                origin.append(copy.deepcopy(i))
            else:
                items.append(i)
        all_of_schema.pop('allOf')
        items = origin + items + [all_of_schema]
        reduce(merge_dict, items)
        return items[0]
