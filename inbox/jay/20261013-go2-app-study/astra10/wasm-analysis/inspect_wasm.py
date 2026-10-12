"""Read-only WASM section inventory and comparison to retained public Git trees."""
import hashlib
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = pathlib.Path(__file__).resolve().parent
TARGETS = [ROOT / 'extracted/assets/dist/assets/libvoxel-Bqa6xB-f.wasm',
           ROOT / 'extracted/assets/dist/assets/libvoxel-doIu-r8s.wasm']

class Reader:
    def __init__(self, data, pos=0): self.data, self.pos = data, pos
    def byte(self):
        out = self.data[self.pos]; self.pos += 1; return out
    def uint(self):
        out = shift = 0
        for _ in range(5):
            b = self.byte(); out |= (b & 127) << shift
            if b < 128: return out
            shift += 7
        raise ValueError('invalid u32 LEB128')
    def name(self):
        n = self.uint(); s = self.data[self.pos:self.pos+n].decode(); self.pos += n; return s
    def limits(self):
        flags = self.uint(); minimum = self.uint()
        return {'flags': flags, 'min_pages': minimum, 'max_pages': self.uint() if flags & 1 else None}

def inspect(path):
    data = path.read_bytes()
    assert data[:8] == b'\x00asm\x01\x00\x00\x00'
    r = Reader(data, 8)
    result = {'path': path.relative_to(ROOT).as_posix(), 'bytes': len(data),
              'sha256': hashlib.sha256(data).hexdigest(),
              'git_blob_sha1': hashlib.sha1(b'blob '+str(len(data)).encode()+b'\x00'+data).hexdigest(),
              'sections': [], 'types': [], 'imports': [], 'function_types': [],
              'memories': [], 'exports': [], 'bodies': []}
    types = {0x7f:'i32', 0x7e:'i64', 0x7d:'f32', 0x7c:'f64'}
    imported_functions = 0
    while r.pos < len(data):
        section_offset = r.pos; section_id = r.byte(); size = r.uint(); start = r.pos; end = start + size
        result['sections'].append({'id': section_id,'section_offset':section_offset,'payload_offset':start,'size':size})
        if section_id == 1:
            for _ in range(r.uint()):
                assert r.byte() == 0x60
                params = [types[r.byte()] for _ in range(r.uint())]
                returns = [types[r.byte()] for _ in range(r.uint())]
                result['types'].append({'params':params,'results':returns})
        elif section_id == 2:
            for _ in range(r.uint()):
                module, name, kind = r.name(), r.name(), r.byte()
                assert kind == 0, 'Unexpected non-function import'
                result['imports'].append({'module':module,'name':name,'type':r.uint()})
                imported_functions += 1
        elif section_id == 3:
            result['function_types'] = [r.uint() for _ in range(r.uint())]
        elif section_id == 5:
            result['memories'] = [r.limits() for _ in range(r.uint())]
        elif section_id == 7:
            for _ in range(r.uint()): result['exports'].append({'name':r.name(),'kind':r.byte(),'index':r.uint()})
        elif section_id == 8:
            result['start_function'] = r.uint()
        elif section_id == 10:
            for i in range(r.uint()):
                length_at = r.pos; n = r.uint(); body_at = r.pos
                locals_count = r.uint()
                local_groups = [{'count':r.uint(),'type':types[r.byte()]} for _ in range(locals_count)]
                result['bodies'].append({'function_index':imported_functions+i,
                    'type_index':result['function_types'][i], 'size_field_offset':length_at,
                    'body_offset':body_at,'instruction_offset':r.pos,'size':n,'end_exclusive':body_at+n,
                    'locals':local_groups})
                r.pos = body_at+n
        r.pos = end
    assert all(x['max_pages'] == x['min_pages'] and x['max_pages'] <= 1536 for x in result['memories'])
    assert 'start_function' not in result
    return result

def tree_matches(targets):
    out = []
    for path in sorted((ROOT/'public-protocol').rglob('*.json')):
        if path.name not in ('metadata.json','branch-3d-tree.json'): continue
        obj = json.loads(path.read_text(encoding='utf-8-sig'))
        def walk(item):
            if isinstance(item,dict):
                if str(item.get('path','')).endswith('.wasm'):
                    matches = [x['path'] for x in targets if item.get('sha') == x['git_blob_sha1']]
                    out.append({'metadata':path.relative_to(ROOT).as_posix(), 'entry':item,'matching_apk_members':matches})
                for v in item.values(): walk(v)
            elif isinstance(item,list):
                for v in item: walk(v)
        walk(obj)
    return out

targets = [inspect(p) for p in TARGETS]
result = {'targets':targets,'public_tree_comparison':tree_matches(targets)}
(OUT/'inventory.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'targets':[{k:x[k] for k in ['path','bytes','sha256','git_blob_sha1','imports','memories','exports','bodies']} for x in targets],
                  'tree_comparison':result['public_tree_comparison']},ensure_ascii=False))
