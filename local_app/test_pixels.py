"""Offline pixel-integrity regressions; fixtures are not generated artwork."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from PIL import Image

from local_app import pixels


def fixture(project, version=1):
    groups = ['01_三视图', '02_表情', '03_服装', '04_道具细节']
    manifest = dict(name='明确标注的离线测试样例', preset='upstream22', revision=1, example=True,
                    unseen_design='测试图形不是角色原作，不能用来证明生图成功。',
                    sections=[dict(group=g, title=g, note='合成 RGB / RGBA 测试') for g in groups],
                    tasks=[], selections={})
    selected = []
    for gi, (group,count) in enumerate(zip(groups,[3,8,4,7])):
        (project/group).mkdir(parents=True,exist_ok=True)
        for n in range(count):
            tid = f'{chr(65+gi)}{n+1:02d}'
            w,h = (48+n,80+n) if gi == 0 else (48+n,48+n)
            image = Image.new('RGBA' if n%2 else 'RGB',(w,h))
            for y in range(h):
                for x in range(w):
                    color = ((x*7+gi*43+n*11)%256,(y*9+n*17)%256,(x+y+gi*31+n*7)%256)
                    image.putpixel((x,y),color+((x*5+y*3+80)%256,) if image.mode == 'RGBA' else color)
            rel = f'{group}/{tid}_v{version:02d}.png'
            image.save(project/rel)
            image.close()
            digest = pixels._hash(project/rel)
            rec = f'00_生成记录/{tid}_v{version:02d}.json'
            (project/'00_生成记录').mkdir(exist_ok=True)
            record = dict(id=tid,group=group,output=rel,output_sha256=digest,dimensions=[w,h],
                          version=version,status='success',review_status='approved',
                          provenance='deterministic_offline_fixture',execution_mode='offline_fixture')
            (project/rec).write_text(json.dumps(record),encoding='utf-8')
            manifest['tasks'].append(dict(id=tid,group=group,label=f'样例 {tid}'))
            manifest['selections'][tid] = version
            selected.append(dict(id=tid,group=group,label=f'样例 {tid}',file=rel,sha256=digest,
                                 width=w,height=h,version=version,record_file=rec))
    return manifest,selected


class PixelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='设定板 test 中文 ')
        cls.base = Path(cls.temp.name)/'baseline'
        cls.base.mkdir()
        cls.manifest,cls.assets = fixture(cls.base)
        cls.export = pixels.compose(cls.base,cls.manifest,cls.assets)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='中文 integrity ')
        self.root = Path(self.directory.name)/'工程 带空格'
        shutil.copytree(self.base,self.root)
        self.m = deepcopy(self.manifest)
        self.a = deepcopy(self.assets)
        self.e = deepcopy(self.export)

    def tearDown(self):
        self.directory.cleanup()

    def index(self):
        return pixels._read(self.root/self.e['index'])

    def change_index(self,callback):
        index = self.index()
        callback(index)
        pixels._atomic_json(self.root/self.e['index'],index)
        self.e['index_sha256'] = pixels._hash(self.root/self.e['index'])

    def expect_failure(self):
        with self.assertRaises(ValueError):
            pixels.verify(self.root,self.m,self.a,self.e)

    def record(self,asset,**changes):
        path = self.root/asset['record_file']
        record = pixels._read(path)
        record.update(changes)
        pixels._atomic_json(path,record)

    def test_complete_twenty_two_rgb_rgba_and_native_slices(self):
        original_cap = Image.MAX_IMAGE_PIXELS
        report = pixels.verify(self.root,self.m,self.a,self.e)
        self.assertTrue(self.e['verified'])
        self.assertEqual((report['byte_match'],report['native_slices_verified']),(22,4))
        self.assertEqual(Image.MAX_IMAGE_PIXELS,original_cap)
        self.assertEqual(len(self.index()['files']),10)
        for entry in self.index()['files']:
            if entry['kind'] != 'native_slice':
                self.assertLessEqual(max(entry['dimensions']),4200 if entry['kind']=='browse' else 4000)

    def test_white_alpha_compositing(self):
        a = self.a[1]
        p = next(p for p in self.index()['placements'] if p['id']==a['id'])
        with Image.open(self.root/a['file']) as source,Image.open(self.root/self.e['master']) as board:
            rgba = source.getpixel((0,0))
            expected = tuple((v*rgba[3]+255*(255-rgba[3])+127)//255 for v in rgba[:3])
            self.assertEqual(board.getpixel((p['x'],p['y'])),expected)

    def test_preview_downsamples_without_upscaling(self):
        with Image.new('RGB',(5000,50),'white') as source:
            preview=pixels._preview(source,4000)
            try:
                self.assertEqual(preview.size,(4000,40))
            finally:
                preview.close()
        with Image.new('RGB',(80,40),'white') as source:
            preview=pixels._preview(source,4200)
            try:
                self.assertEqual(preview.size,(80,40))
            finally:
                preview.close()

    def test_missing_master_is_failure(self):
        (self.root/self.e['master']).unlink()
        self.expect_failure()

    def test_missing_index_is_failure(self):
        (self.root/self.e['index']).unlink()
        self.expect_failure()

    def test_missing_asset_is_failure(self):
        (self.root/self.a[0]['file']).unlink()
        self.expect_failure()

    def test_empty_manifest_is_failure(self):
        self.m['tasks']=[]
        self.expect_failure()

    def test_empty_placements_is_failure(self):
        self.change_index(lambda i:i.update(placements=[]))
        self.expect_failure()

    def test_omitted_placement_is_failure(self):
        self.change_index(lambda i:i['placements'].pop())
        self.expect_failure()

    def test_extra_placement_is_failure(self):
        self.change_index(lambda i:i['placements'].append(deepcopy(i['placements'][0])))
        self.expect_failure()

    def test_duplicate_placement_id_is_failure(self):
        self.change_index(lambda i:i['placements'][1].update(id=i['placements'][0]['id']))
        self.expect_failure()

    def test_wrong_group_is_failure(self):
        self.change_index(lambda i:i['placements'][0].update(group='04_道具细节'))
        self.expect_failure()

    def test_substituted_asset_is_failure(self):
        self.change_index(lambda i:i['placements'][0].update(file=self.a[1]['file']))
        self.expect_failure()

    def test_wrong_record_hash_is_failure(self):
        self.record(self.a[0],output_sha256='0'*64)
        self.expect_failure()

    def test_wrong_record_dimensions_is_failure(self):
        self.record(self.a[0],dimensions=[1,1])
        self.expect_failure()

    def test_failed_record_is_failure(self):
        self.record(self.a[0],status='failed')
        self.expect_failure()

    def test_fixture_cannot_impersonate_production_artwork(self):
        self.m['example']=False
        with self.assertRaises(ValueError):
            pixels.compose(self.root,self.m,self.a)

    def test_review_not_approved_is_failure(self):
        self.record(self.a[0],review_status='awaiting_review')
        self.expect_failure()

    def test_stale_record_is_failure(self):
        self.record(self.a[0],stale=True)
        self.expect_failure()

    def test_selected_v02_cannot_silently_verify_v01(self):
        self.m['selections'][self.a[0]['id']]=2
        self.expect_failure()

    def test_version_two_is_composed_and_verified(self):
        a = self.a[0]
        new_rel = a['file'].replace('_v01','_v02')
        with Image.open(self.root/a['file']) as im:
            im.putpixel((0,0),(1,2,3))
            im.save(self.root/new_rel)
        old_record = pixels._read(self.root/a['record_file'])
        a.update(file=new_rel,sha256=pixels._hash(self.root/new_rel),version=2,
                 record_file=a['record_file'].replace('_v01','_v02'))
        old_record.update(output=new_rel,output_sha256=a['sha256'],version=2)
        pixels._atomic_json(self.root/a['record_file'],old_record)
        self.m['selections'][a['id']]=2
        export = pixels.compose(self.root,self.m,self.a)
        self.assertEqual(export['directory'],'exports/v002')
        self.assertEqual(pixels.verify(self.root,self.m,self.a,export)['byte_match'],22)
        self.assertTrue((self.root/'exports/v001/master.png').is_file())

    def test_duplicate_asset_is_failure(self):
        self.a[1].update(file=self.a[0]['file'],sha256=self.a[0]['sha256'],
                         width=self.a[0]['width'],height=self.a[0]['height'])
        self.record(self.a[1],output=self.a[1]['file'],output_sha256=self.a[1]['sha256'],
                    dimensions=[self.a[1]['width'],self.a[1]['height']])
        self.expect_failure()

    def test_scaled_placement_is_failure(self):
        self.change_index(lambda i:i['placements'][0].update(scale=.5))
        self.expect_failure()

    def test_wrong_placement_dimension_is_failure(self):
        self.change_index(lambda i:i['placements'][0].update(width=1))
        self.expect_failure()

    def test_overlapping_cells_is_failure(self):
        self.change_index(lambda i:i['placements'][1].update(cell=i['placements'][0]['cell']))
        self.expect_failure()

    def test_out_of_bounds_cell_is_failure(self):
        self.change_index(lambda i:i['placements'][0].update(cell=[-1,0,10,10]))
        self.expect_failure()

    def test_changed_placed_pixel_despite_updated_hash_and_success_claim(self):
        p=self.index()['placements'][0]
        with Image.open(self.root/self.e['master']) as im:
            color=im.getpixel((p['x'],p['y']))
            im.putpixel((p['x'],p['y']),((color[0]+1)%256,color[1],color[2]))
            im.save(self.root/self.e['master'])
        digest=pixels._hash(self.root/self.e['master'])
        self.e['master_sha256']=digest
        self.change_index(lambda i:i.update(master_sha256=digest,verification=[{'pixel_match':True}]))
        self.expect_failure()

    def test_wrong_master_selection_is_failure(self):
        (self.root/self.e['master']).rename(self.root/'exports/v001/aaa_原像素.png')
        self.e['master']='exports/v001/aaa_原像素.png'
        self.expect_failure()

    def test_old_unrelated_glob_master_is_ignored(self):
        (self.root/'exports/v001/aaa_原像素.png').write_bytes(b'not an image')
        self.assertTrue(pixels.verify(self.root,self.m,self.a,self.e)['verified'])

    def test_index_hash_is_independently_checked(self):
        path=self.root/self.e['index']
        path.write_text(path.read_text(encoding='utf-8')+' ',encoding='utf-8')
        self.expect_failure()

    def test_native_slice_alteration_is_failure(self):
        entry=next(f for f in self.index()['files'] if f['kind']=='native_slice')
        with Image.open(self.root/entry['file']) as im:
            im.putpixel((0,0),(0,0,0))
            im.save(self.root/entry['file'])
        digest=pixels._hash(self.root/entry['file'])
        self.change_index(lambda i:next(f for f in i['files'] if f['file']==entry['file']).update(sha256=digest))
        self.expect_failure()

    def test_wrong_slice_group_is_failure(self):
        self.change_index(lambda i:next(f for f in i['files'] if f['kind']=='native_slice').update(group='02_表情'))
        self.expect_failure()

    def test_path_escape_is_failure(self):
        self.a[0]['file']='../outside.png'
        self.expect_failure()

    def test_windows_absolute_path_is_failure(self):
        self.a[0]['file']='C:/private.png'
        self.expect_failure()

    def test_invalid_record_path_is_failure(self):
        self.a[0]['record_file']='..\\outside.json'
        self.expect_failure()

    def test_manifest_revision_invalidation(self):
        self.m['revision']=2
        self.expect_failure()

    def test_memory_budget_blocks_before_export(self):
        with self.assertRaises(ValueError):
            pixels.compose(self.root,self.m,self.a,{'max_memory_mb':64})
        self.assertFalse((self.root/'exports/v002').exists())

    def test_missing_font_is_actionable(self):
        with self.assertRaisesRegex(ValueError,'字体'):
            pixels.compose(self.root,self.m,self.a,{'font':str(self.root/'missing.ttf')})

    def test_custom_counts_need_all_four_nonempty_sections(self):
        self.m['preset']='custom'
        self.m['tasks']=self.m['tasks'][:1]
        self.a=self.a[:1]
        self.m['selections']={self.a[0]['id']:1}
        with self.assertRaises(ValueError):
            pixels.compose(self.root,self.m,self.a)

    def test_malformed_placements_are_value_errors(self):
        self.change_index(lambda i:i.update(placements=['bad']*22))
        self.expect_failure()


if __name__=='__main__':
    unittest.main()
