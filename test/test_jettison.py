# encoding: utf-8

import math

import pytest
import six

import jettison


codec_tests = {
    'boolean': {
        'size': 1,
        'type': bool,
        'tests': {
            True: [1],
            False: [0],
        }
    },
    'int8': {
        'size': 1,
        'type': int,
        'tests': {
            -128: [128],
            127: [127],
        },
    },
    'int16': {
        'size': 2,
        'type': int,
        'tests': {
            -32768: [128, 0],
            32767: [127, 255],
        },
    },
    'int32': {
        'size': 4,
        'type': int,
        'tests': {
            -2147483648: [128, 0, 0, 0],
            2147483647: [127, 255, 255, 255],
        },
    },
    'uint8': {
        'size': 1,
        'type': int,
        'tests': {
            0: [0],
            255: [255],
        },
    },
    'uint16': {
        'size': 2,
        'type': int,
        'tests': {
            0: [0, 0],
            65535: [255, 255],
        },
    },
    'uint32': {
        'size': 4,
        'type': int,
        'tests': {
            0: [0, 0, 0, 0],
            4294967295: [255, 255, 255, 255],
        },
    },
    'float32': {
        'size': 4,
        'type': float,
        'tests': {
            float(0): [0, 0, 0, 0],
            float(1): [63, 128, 0, 0],
            float(-1): [191, 128, 0, 0],
            float(2): [64, 0, 0, 0],
            float(-2): [192, 0, 0, 0],
            float(0.5): [63, 0, 0, 0],
            float(-0.5): [191, 0, 0, 0],
            float('inf'): [127, 128, 0, 0],
            float('-inf'): [255, 128, 0, 0],
            float('nan'): [127, 192, 0, 0],
        }
    },
    'float64': {
        'size': 8,
        'type': float,
        'tests': {
            float(0): [0, 0, 0, 0, 0, 0, 0, 0],
            float(1): [63, 240, 0, 0, 0, 0, 0, 0],
            float(-1): [191, 240, 0, 0, 0, 0, 0, 0],
            float(2): [64, 0, 0, 0, 0, 0, 0, 0],
            float(-2): [192, 0, 0, 0, 0, 0, 0, 0],
            float(0.1): [63, 185, 153, 153, 153, 153, 153, 154],
            float(-0.1): [191, 185, 153, 153, 153, 153, 153, 154],
            float(1.0000001): [63, 240, 0, 0, 26, 215, 242, 155],
            float('inf'): [127, 240, 0, 0, 0, 0, 0, 0],
            float('-inf'): [255, 240, 0, 0, 0, 0, 0, 0],
            float('nan'): [127, 248, 0, 0, 0, 0, 0, 0],
        }
    }
}

flattened_codec_tests = []
for codec_key, expected in codec_tests.items():
    codec = jettison._codecs[codec_key]
    for value, expected_dumped_value in expected['tests'].items():
        flattened_codec_tests.append([codec, expected['size'], expected['type'],
                                      value, expected_dumped_value])


@pytest.mark.parametrize(
    'codec,expected_size,expected_type,value,expected_dumped_value',
    flattened_codec_tests)
def test_codecs(codec, expected_size, expected_type, value,
                expected_dumped_value):
    # FIXME: test little endian
    assert codec.size == expected_size
    dumped_value = codec.dumps(value)
    assert isinstance(dumped_value, six.binary_type)
    assert bytearray(dumped_value) == bytearray(expected_dumped_value)
    loaded_value = codec.loads(dumped_value)
    if math.isnan(value):
        assert math.isnan(loaded_value)
    else:
        assert loaded_value == value
    assert isinstance(loaded_value, expected_type)


def test_array_codec():
    codec = jettison.ArrayCodec('d')
    assert not hasattr(codec, 'size')

    # dumping an iterable should write a length and each dumped value
    values = (0.1, 0.2, 0.3, 0.4, 0.5)
    dumped_values = codec.dumps(values)
    assert dumped_values == (
        b'\x00\x00\x00\x05'                  # length
        b'\x3F\xB9\x99\x99\x99\x99\x99\x9A'  # value 0
        b'\x3F\xC9\x99\x99\x99\x99\x99\x9A'  # value 1
        b'\x3F\xD3\x33\x33\x33\x33\x33\x33'  # value 2
        b'\x3F\xD9\x99\x99\x99\x99\x99\x9A'  # value 3
        b'\x3F\xE0\x00\x00\x00\x00\x00\x00'  # value 4
    )
    assert codec.loads(dumped_values) == values
    assert codec.size == len(dumped_values)

    # dumping an empty iterable should just write a zero length
    values = ()
    dumped_values = codec.dumps(values)
    assert dumped_values == b'\x00\x00\x00\x00'
    assert codec.loads(dumped_values) == values
    assert codec.size == len(dumped_values)


def test_string_codec():
    codec = jettison._codecs['string']
    assert not hasattr(codec, 'size')

    # dumping a unicode string should write a length and a utf-8 encoded string
    value = u'hodør'
    dumped_value = codec.dumps(value)
    assert dumped_value == b'\x00\x00\x00\x06' + value.encode('utf-8')
    assert codec.loads(dumped_value) == value
    assert codec.size == len(dumped_value)

    # dumping an empty unicode string should just write a zero length
    value = u''
    dumped_value = codec.dumps(value)
    assert dumped_value == b'\x00\x00\x00\x00'
    assert codec.loads(dumped_value) == value
    assert codec.size == len(dumped_value)


def test_float_codec_javascript_nan():
    """
    JS encodes NaN slightly different (but there is flexibility in IEEE 754
    encoding, so it should be fine). Make sure Python parses it as NaN.
    """
    codec = jettison._codecs['float32']
    assert math.isnan(codec.loads(b'\x7F\x80\x00\x01'))
    codec = jettison._codecs['float64']
    assert math.isnan(codec.loads(b'\x7F\xF0\x00\x00\x00\x00\x00\x01'))


def test_definition():
    definition = jettison.define([
        {'key': 'entity_id', 'type': 'int32'},
        {'key': 'x', 'type': 'float64'},
        {'key': 'y', 'type': 'float64'},
        {'key': 'points', 'type': 'array', 'value_type': 'float64'},
        {'key': 'health', 'type': 'int16'},
    ])
    value = {'entity_id': 1,
             'x': 0.5,
             'y': 1.5,
             'points': (0.1, 0.2, 0.3, 0.4),
             'health': 100}
    dumped_value = definition.dumps(value)
    assert dumped_value == (
        b'\x00\x00\x00\x01'                  # entity id
        b'\x3F\xE0\x00\x00\x00\x00\x00\x00'  # x
        b'\x3F\xF8\x00\x00\x00\x00\x00\x00'  # y
        b'\x00\x00\x00\x04'                  # points length
        b'\x3F\xB9\x99\x99\x99\x99\x99\x9A'  # points 0
        b'\x3F\xC9\x99\x99\x99\x99\x99\x9A'  # points 1
        b'\x3F\xD3\x33\x33\x33\x33\x33\x33'  # points 2
        b'\x3F\xD9\x99\x99\x99\x99\x99\x9A'  # points 3
        b'\x00\x64'                          # health
    )
    assert definition.loads(dumped_value) == value


def test_schema():
    schema = jettison.Schema()
    schema.define('spawn', [
        {'key': 'entity_id', 'type': 'int32'},
        {'key': 'x', 'type': 'float64'},
        {'key': 'y', 'type': 'float64'},
        {'key': 'points', 'type': 'array', 'value_type': 'float64'},
        {'key': 'health', 'type': 'int16'},
    ])
    schema.define('position', [
        {'key': 'entity_id', 'type': 'int32'},
        {'key': 'x', 'type': 'float64'},
        {'key': 'y', 'type': 'float64'},
    ])

    # try dumping a spawn packet
    value = {'entity_id': 1,
             'x': 0.5,
             'y': 1.5,
             'points': (0.1, 0.2, 0.3, 0.4),
             'health': 100}
    dumped_value = schema.dumps('spawn', value)
    assert dumped_value == (
        b'\x01'                              # definition id
        b'\x00\x00\x00\x01'                  # entity id
        b'\x3F\xE0\x00\x00\x00\x00\x00\x00'  # x
        b'\x3F\xF8\x00\x00\x00\x00\x00\x00'  # y
        b'\x00\x00\x00\x04'                  # points length
        b'\x3F\xB9\x99\x99\x99\x99\x99\x9A'  # points 0
        b'\x3F\xC9\x99\x99\x99\x99\x99\x9A'  # points 1
        b'\x3F\xD3\x33\x33\x33\x33\x33\x33'  # points 2
        b'\x3F\xD9\x99\x99\x99\x99\x99\x9A'  # points 3
        b'\x00\x64'                          # health
    )
    assert schema.loads(dumped_value) == value

    # try dumping a position packet
    value = {'entity_id': 1,
             'x': -123.456,
             'y': 7.89}
    dumped_value = schema.dumps('position', value)
    assert dumped_value == (
        b'\x02'                              # definition id
        b'\x00\x00\x00\x01'                  # entity id
        b'\xC0\x5E\xDD\x2F\x1A\x9F\xBE\x77'  # x
        b'\x40\x1F\x8F\x5C\x28\xF5\xC2\x8F'  # y
    )
    assert schema.loads(dumped_value) == value
