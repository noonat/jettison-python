"""
Jettison
~~~~~~~~

Jettison is a library for encoding binary data into strings for transmission
to JavaScript clients using things like WebSockets. This Python module is
compatible with the JavaScript version at <https://github.com/noonat/jettison>.

Use Jettison to define a shared schema between the client and the server.
Each schema can contain a number of definitions, and each definition can have
a number of fields. You can then encode dictionaries, where each field in the
definition maps to a key in the dictionary.

Here's an example schema with two packets:

    >>> import jettison
    >>> schema = jettison.Schema()
    >>> schema.define('spawn', [
    ...     {'key': 'entity_id', 'type': 'uint32'},
    ...     {'key': 'x', 'type': 'float64'},
    ...     {'key': 'y', 'type': 'float64'},
    ...     {'key': 'health', 'type': 'int16'},
    ... ])
    <jettison.Definition object at 0x10fe6fd50>
    >>> schema.define('health', [
    ...     {'key': 'entity_id', 'type': 'uint32'},
    ...     {'key': 'health', 'type': 'int16'}
    ... ])
    <jettison.Definition object at 0x10fe82110>

You can then use the schema to dump a spawn dict:

    >>> schema.dumps('spawn', {
    ...     'entity_id': 1,
    ...     'x': 0.5,
    ...     'y': -1.5,
    ...     'health': 100,
    ... })
    '\x01\x00\x00\x00\x01?\xe0\x00\x00\x00\x00\x00\x00\xbf\xf8\x00...'

Or load a string:

    >>> schema.loads(_)
    {'y': -1.5, 'x': 0.5, 'entity_id': 1, 'health': 100}

Note that you don't need to specify the definition type on load, as the
definition id is encoded into the packet. This is why the schemas must match
on the client and server.

Types that are currently supported are:

+---------+------------------------------------------------------------------+
| Type    | Description                                                      |
+=========+==================================================================+
| int8    | 1 byte signed integer. Range is -128 to 127 (inclusive).         |
+---------+------------------------------------------------------------------+
| int16   | 2 byte signed integer. Range is -32768 to 32767.                 |
+---------+------------------------------------------------------------------+
| int32   | 4 byte signed integer. Range is -2147483648 to 2147483647.       |
+---------+------------------------------------------------------------------+
| uint8   | 1 byte unsigned integer. Range is 0 to 255.                      |
+---------+------------------------------------------------------------------+
| uint16  | 2 byte unsigned integer. Range is 0 to 65535.                    |
+---------+------------------------------------------------------------------+
| uint32  | 4 byte unsigned integer. Range is 0 to 4294967295.               |
+---------+------------------------------------------------------------------+
| float32 | 4 byte floating point number. Note that normal JavaScript        |
|         | numbers will be rounded to fit this size, so decoded values      |
|         | will only approximately equal the originals.                     |
+---------+------------------------------------------------------------------+
| float64 | 8 byte floating point number. Normal JavaScript numbers are      |
|         | stored in this format, so these will be transmitted without      |
|         | rounding.                                                        |
+---------+------------------------------------------------------------------+
| array   | A variable length array of another type. When you use this type, |
|         | you must also specify a `valueType` field, which will specify    |
|         | the type of value in the array.                                  |
+---------+------------------------------------------------------------------+
| string  | A variable length string. JavaScript's UTF-16 strings are        |
|         | encoded to UTF-8 for transmission.                               |
+---------+------------------------------------------------------------------+

Note that if you attempt to encode a value that is out of range of its type,
an exception will be raised.
"""

import struct

import six


#: This struct is used to encode big endian length values.
_big_length_struct = struct.Struct('>I')

#: This struct is used to encode little endian length values.
_little_length_struct = struct.Struct('<I')


def _get_length_struct(little_endian):
    """
    Return the appropriate length struct for the given endianness.

    :param bool little_endian:
    :returns: struct.Struct
    """
    if little_endian:
        return _little_length_struct
    else:
        return _big_length_struct


class Codec(object):

    """
    This class is just a thin abstraction around the struct module.

    :param str format: Python struct module format string for the values that
        this codec will encode and decode. That is, if you want the codec to
        encode unsigned 32-bit integers, this should be 'I'. The format string
        should not include any endian prefixes.
    """

    def __init__(self, format):
        super(Codec, self).__init__()
        self.format = format
        self.big_struct = struct.Struct('>{}'.format(self.format))
        self.little_struct = struct.Struct('<{}'.format(self.format))
        self.size = struct.calcsize(self.format)

    def _get_struct(self, little_endian):
        """
        Get the appropriate struct for the given endianness.

        :param bool little_endian: If True, values will be encoded in little
            endian format.
        :returns: struct.Struct
        """
        if little_endian:
            return self.little_struct
        else:
            return self.big_struct

    def dumps(self, value, little_endian=False):
        """
        Dump the value to a string.

        :param value: Value of the type specified in the format string.
        :param bool little_endian: If True, values will be decoded in little
            endian format.
        :returns: str
        """
        return self._get_struct(little_endian).pack(value)

    def loads(self, string, offset=0, little_endian=False):
        """
        Load the value from a string.

        :param str string: A string encoded by this codec. This should be a str
            object on Python 2, and a bytes object on Python 3.
        :param int offset: Start decoding from this offset within the string.
        :param bool little_endian: If True, values will be decoded in little
            endian format.
        :returns:
        """
        return self._get_struct(little_endian).unpack_from(string, offset)[0]


class ArrayCodec(object):

    """
    An array codec is a special case. It starts with a uint32 length value,
    followed by that many items in the passed value_format.

    :param str value_format: Format string for the list items.
    """

    def __init__(self, value_format):
        super(ArrayCodec, self).__init__()
        self.value_format = value_format
        self.big_format_template = '>{{length}}{}'.format(self.value_format)
        self.little_format_template = '<{{length}}{}'.format(self.value_format)

    def _get_format(self, length, little_endian):
        """
        Get the appropriate format for the given length and endianness.

        :param int length: The number of items in the list.
        :param bool little_endian: If True, values will be encoded in little
            endian format.
        :returns: str
        """
        if little_endian:
            return self.little_format_template.format(length=length)
        else:
            return self.big_format_template.format(length=length)

    def dumps(self, values, little_endian=False):
        """
        Dump a list of values to a string.

        :param list values: List of values to encode. Each value must be of a
            type compatible with the value_format specified when the ArrayCodec
            was constructed.
        :param bool little_endian: If True, values will be encoded in little
            endian format.
        :returns: str
        """
        length = len(values)
        length_struct = _get_length_struct(little_endian)
        string = length_struct.pack(length)
        string += struct.pack(self._get_format(length, little_endian), *values)
        return string

    def loads(self, string, offset=0, little_endian=False):
        """
        Load a list of values from a string.

        :param str string: A string encoded by this codec. This should be a str
            object on Python 2, and a bytes object on Python 3.
        :param int offset: Start decoding from this offset within the string.
        :param bool little_endian: If True, values will be decoded in little
            endian format.
        :returns: tuple
        """
        length_struct = _get_length_struct(little_endian)
        length = length_struct.unpack_from(string, offset)[0]
        if length:
            format = self._get_format(length, little_endian)
            self.size = struct.calcsize(format) + length_struct.size
            return struct.unpack_from(format, string,
                                      offset + length_struct.size)
        else:
            self.size = length_struct.size
            return ()


class StringCodec(object):

    """
    The string codec is another special case. The codec first converts the
    unicode string to UTF-8, then packs that. The packed value is prefixed
    with the length of the UTF-8 string, like the ArrayCodec.
    """

    def __init__(self):
        super(StringCodec, self).__init__()
        self.big_format_template = '>{length}s'
        self.little_format_template = '<{length}s'

    def _get_format(self, length, little_endian):
        """
        Get the appropriate format for the given length and endianness.

        :param int length: The number of items in the list.
        :param bool little_endian: If True, values will be encoded in little
            endian format.
        :returns: str
        """
        if little_endian:
            return self.little_format_template.format(length=length)
        else:
            return self.big_format_template.format(length=length)

    def dumps(self, value, little_endian=False):
        """
        :param unicode value: A unicode string to encode.
        :param bool little_endian: If True, values will be encoded in little
            endian format.
        :returns str:
        """
        # FIXME: raise a better error message here
        assert isinstance(value, six.text_type)
        value = value.encode('utf-8')
        length = len(value)
        length_struct = _get_length_struct(little_endian)
        format = self._get_format(length, little_endian)
        return (length_struct.pack(length) + struct.pack(format, value))

    def loads(self, string, offset=0, little_endian=False):
        """
        :param str string: A string encoded by this codec. This should be a str
            object on Python 2, and a bytes object on Python 3.
        :param int offset: Start decoding from this offset within the string.
        :param bool little_endian: If True, values will be decoded in little
            endian format.
        :returns: unicode
        """
        length_struct = _get_length_struct(little_endian)
        length = length_struct.unpack_from(string, offset)[0]
        if length:
            format = self._get_format(length, little_endian)
            self.size = struct.calcsize(format) + length_struct.size
            value = struct.unpack_from(format, string,
                                       offset + length_struct.size)[0]
            return value.decode('utf-8')
        else:
            self.size = length_struct.size
            return u''


#: Mapping of types to the codecs objects for those types. Note that the
#: "array" type is not present in this list because its value_type field means
#: it must be constructed on the fly.
_codecs = {
    'boolean': Codec('?'),
    'float32': Codec('f'),
    'float64': Codec('d'),
    'int8': Codec('b'),
    'int16': Codec('h'),
    'int32': Codec('i'),
    'string': StringCodec(),
    'uint8': Codec('B'),
    'uint16': Codec('H'),
    'uint32': Codec('I')
}


class Field(object):

    """
    Fields represent a single property in an object. These fields are grouped
    into definition objects. Each field represents a single key from the type
    of dict that will be encoded by the definition.

    :param str key: Key in the dictionary to encode.
    :param str type: Type of the value in the dictionary. This should be one
        of the supported codec types (e.g. "int32").
    :param str value_type: If type is "array", this should specify the type of
        the values within the array.
    """

    def __init__(self, key, type, value_type=None):
        super(Field, self).__init__()
        self.key = key
        self.type = type
        self.value_type = value_type
        if not self.key:
            raise ValueError('key is required')
        if self.type == 'array':
            if (self.value_type in ('array', 'string') or
                    self.value_type not in _codecs):
                raise ValueError('invalid array value type %r' %
                                 (self.value_type,))
            self.codec = ArrayCodec(_codecs[self.value_type].format)
        elif self.type in _codecs:
            self.codec = _codecs[self.type]
        else:
            raise ValueError('invalid type %r' % (self.type,))


class Definition(object):

    """
    Definitions are a grouping of fields, and are used to encode or decode an
    individual message. They can be grouped into schemas or used standalone.

    :param list(Field) fields: The fields contained in this definition.
    :param int id: An optional integer id for this definition. Use to identify
        it in packets encoded by a schema.
    :param str key: An optional human readable name for this definition. Used
        to identify it within a schema.
    :param bool little_endian: If True, values will be encoded and decoded in
        little endian format for this definition.
    """

    def __init__(self, fields, id=None, key=None, little_endian=False):
        super(Definition, self).__init__()
        self.fields = fields
        self.id = id
        self.key = key
        self.little_endian = little_endian

    def dumps(self, data):
        """
        :param data: The data dict to encode as a string.
        :returns: str
        """
        string = b''
        for field in self.fields:
            string += field.codec.dumps(data[field.key], self.little_endian)
        return string

    def loads(self, string, offset=0):
        """
        :param str string: A string encoded by this definition. This should be
            a str object on Python 2, and a bytes object on Python 3.
        :returns: dict
        """
        if isinstance(string, six.text_type):
            string = string.encode('utf-8')
        values = {}
        for field in self.fields:
            values[field.key] = field.codec.loads(string, offset,
                                                   self.little_endian)
            offset += field.codec.size
        return values


class Schema(object):

    """
    A schema is a grouping of definitions. It allows you to encode packets
    by name, in a way that can be decoded automatically by a matching schema
    on the other end of a connection, as long as your packet types are defined
    the same way on both ends.

    :param str id_type: Field type to use for packet type ids.
    """

    # FIXME: automatically set the id type depending on the number of packets
    # that are defined in the schema

    def __init__(self, id_type='uint8'):
        self.definitions = {}
        self.definitions_by_id = {}
        self.id_type = id_type
        self.next_definition_id = 1

    def define(self, key, fields):
        """
        Define a new packet type for the schema.

        :param str key: A name for the definition.
        :param list(dict) fields: Fields for the definition.
        :returns: Definition
        """
        definition = Definition([Field(**kwargs) for kwargs in fields],
                                self.next_definition_id, key)
        self.next_definition_id += 1
        self.definitions[key] = definition
        self.definitions_by_id[definition.id] = definition
        return definition

    def dumps(self, key, data):
        """
        Dump a dict to a string.

        :param str key: Name of the definition.
        :param dict data: Data dict to encode as a string.
        :returns: str
        """
        definition = self.definitions.get(key)
        if definition is None:
            raise KeyError('key {!r} is not defined in schema'.format(key))
        id_codec = _codecs[self.id_type]
        return id_codec.dumps(definition.id) + definition.dumps(data)

    def loads(self, string):
        """
        Load a dict from a string.

        :param str string: A string encoded by a matching schema. This should
            be a str object on Python 2, and a bytes object on Python 3.
        :returns: dict
        """
        # FIXME: this should be able to take an offset.
        id_codec = _codecs[self.id_type]
        definition_id = id_codec.loads(string)
        definition = self.definitions_by_id.get(definition_id)
        if definition is None:
            raise KeyError('id {!r} is not defined in schema'.format(
                definition_id))
        return definition.loads(string, id_codec.size)


def define(field_kwargs):
    """
    Create a new definition object.

    :param list(dict) field_kwargs: List of fields in the definition.
    :returns: Definition
    """
    return Definition([Field(**kwargs) for kwargs in field_kwargs])
