"""Small, defensive FLP metadata reader for mixer context.

It intentionally reads only the documented event stream. It never executes plugin
code or trusts paths embedded in a project. Unknown events are skipped.
"""
import struct


def _varint(data, pos):
    value = shift = 0
    while True:
        if pos >= len(data) or shift > 35:
            raise ValueError('FLP varint inválido')
        b = data[pos]; pos += 1
        value |= (b & 0x7f) << shift
        if not b & 0x80:
            return value, pos
        shift += 7


def _text(payload):
    if len(payload) < 2:
        return ''
    end = len(payload)
    for i in range(0, len(payload) - 1, 2):
        if payload[i:i + 2] == b'\0\0':
            end = i
            break
    raw = payload[:end]
    try:
        return raw.decode('utf-16le', 'replace').strip()
    except UnicodeDecodeError:
        return ''


def parse(path):
    data = path.read_bytes()
    if len(data) > 10 * 1024 * 1024 or data[:4] != b'FLhd':
        raise ValueError('Arquivo FLP inválido ou acima do limite.')
    header_len = struct.unpack_from('<I', data, 4)[0]
    data_header = 8 + header_len
    if len(data) < data_header + 8 or data[data_header:data_header + 4] != b'FLdt':
        raise ValueError('Bloco de dados FLP ausente.')
    data_start = data_header + 8
    fl_version = data[data_start:data_start + 80].decode('ascii', 'ignore').split('\0', 1)[0]
    length = struct.unpack_from('<I', data, data_header + 4)[0]
    end = min(len(data), data_start + length)
    pos = data_start
    events = []
    while pos < end:
        opcode = data[pos]; pos += 1
        if opcode == 0xac:  # FL 25+ three-byte exception
            payload = data[pos:pos + 3]; pos += 3; kind = 'blob'
        elif opcode >= 0xc0:
            size, pos = _varint(data, pos)
            payload = data[pos:pos + size]; pos += size; kind = 'blob'
        elif opcode < 0x40:
            payload = data[pos:pos + 1]; pos += 1; kind = 'u8'
        elif opcode < 0x80:
            payload = data[pos:pos + 2]; pos += 2; kind = 'u16'
        else:
            payload = data[pos:pos + 4]; pos += 4; kind = 'u32'
        if pos > end:
            raise ValueError('FLP truncado')
        value = int.from_bytes(payload, 'little', signed=False) if kind != 'blob' else None
        events.append((opcode, kind, payload, value))

    channels = []
    inserts = []
    current_channel = None
    current_insert = None
    slots = []
    tempo = None
    for opcode, kind, payload, value in events:
        if opcode == 0x40:
            current_channel = {'name': '', 'kind': 'other'}
            channels.append(current_channel)
            current_insert = None
        elif opcode == 0x62 and current_insert is not None:
            slots.append({'index': value, 'name': slots[-1].get('name', '') if slots else ''})
        elif opcode == 0xcb and kind == 'blob':
            name = _text(payload)
            if current_insert is None and current_channel is not None:
                current_channel['name'] = name
            elif current_insert is not None and name:
                # The name immediately before a slot boundary is its plugin name.
                current_insert['_pending'] = name
        elif opcode == 0xcc and kind == 'blob':
            if current_insert is not None:
                current_insert['name'] = _text(payload) or current_insert['name']
        elif opcode == 0x93 and kind == 'u32' and current_insert is not None:
            current_insert['route_to'] = value
            current_insert['slots'] = slots[:10]
            inserts.append(current_insert)
            current_insert = None; slots = []
        elif opcode == 0x62 and current_insert is None:
            current_insert = {'name': '', 'slots': []}
        elif opcode == 0xc9 and kind == 'blob' and current_insert is not None:
            name = _text(payload)
            if name and name.lower() != 'fruity wrapper':
                current_insert['_pending'] = name
        elif opcode == 0x9c and kind == 'u32':
            tempo = value / 1000
    for insert in inserts:
        pending = insert.pop('_pending', '')
        if pending and not insert['slots']:
            insert['slots'] = [{'index': 0, 'name': pending}]
        for slot in insert['slots']:
            slot['name'] = slot.get('name') or pending
    return {'format': 'FLP', 'fl_version': fl_version, 'tempo': tempo,
            'channels': channels[:128], 'mixer_inserts': inserts[:128],
            'warnings': ['FLP é contexto declarado; plugins não são executados nem seus parâmetros são aplicados.']}
