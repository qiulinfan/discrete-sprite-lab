"""Offline endpoint, anchor, resume and shared-budget regression checks."""
import base64
import json
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image,ImageDraw

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import hybrid_actions as H
import pixellab_actions as P


def frame(index):
    im=Image.new('RGBA',(64,64));d=ImageDraw.Draw(im)
    d.rectangle((20+index,20,30+index,45),fill=(100+index*7,80,40,255))
    return im


class FakeAPI:
    def __init__(self):
        self.credit=10.;self.posts=[];self.payloads={};self.get_failure=False;self.uncertain=False
    def call(self,method,endpoint,body=None):
        if endpoint=='/balance':return {'credits':{'usd':self.credit},'subscription':{'generations':0}}
        if method=='POST':
            self.posts.append(body)
            if self.uncertain:raise P.APIError('observation lost',500)
            self.credit-=.02;job=str(len(self.posts));self.payloads[job]=body
            return {'background_job_id':job}
        if self.get_failure:raise P.APIError('temporary retrieval failure',403)
        body=self.payloads[endpoint.rsplit('/',1)[-1]]
        return {'status':'completed','last_response':{'images':[{'base64':base64.b64encode(P.png(frame(i+1))).decode()} for i in range(body['frame_count']+1)]}}


class HybridTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)
        for i in range(6):frame(i).save(self.base/f'{i}.png')
        self.budget=self.base/'evidence/budget.json'
        P.save(self.budget,{'status':'open','authority':'synthetic test authority; no real credits','usd':1.,'max_jobs':10,'reserve_usd_per_job':.05,'jobs':[]})
        self.c={'schema_version':2,'action':'test','route':'keyframed','controller_or_pose_authority':'explicit fixture key poses',
                'image_size':[64,64],'frame_count':5,'frame_ms':80,'loop':False,'pivot':[32,3],'ppu':'fixture family',
                'budget_file':'evidence/budget.json','directions':[{'direction':'south','keys':[{'frame':0,'path':'0.png','phase':'ready'},{'frame':4,'path':'5.png','phase':'impact'}]}]}
        self.path=self.base/'plan.json';self.root=self.base/'out';self.api=FakeAPI()
    def tearDown(self):self.tmp.cleanup()
    def prepare(self):P.save(self.path,self.c);H.prepare(self.path,self.root)

    def test_intermediate_frames_cannot_replace_exact_keys(self):
        self.prepare();H.run(self.root,self.api);H.assemble(self.root)
        self.assertEqual((self.root/'generated/south/frame-00.png').read_bytes(),(self.base/'0.png').read_bytes())
        self.assertEqual((self.root/'generated/south/frame-04.png').read_bytes(),(self.base/'5.png').read_bytes())
        self.assertEqual(len(self.api.posts),1)
        self.assertIn('last_frame',self.api.posts[0]);self.assertIn('first_frame',self.api.posts[0])
        self.assertNotEqual((self.root/'evidence/api/south-000-004/raw/frame-00.png').read_bytes(),(self.base/'0.png').read_bytes())
        m=P.load(self.root/'generated/manifest.json');self.assertEqual([x['origin'] for x in m['frames']],['authored-key']+['pixellab-inbetween']*3+['authored-key'])
        self.assertNotIn('sha256',json.dumps(m))
        with Image.open(self.root/'generated/south-slow.png') as a:
            a.seek(4);self.assertEqual(a.info['duration'],2340)

    def test_loop_wrap_targets_the_original_first_key(self):
        keys=[{'frame':i,'path':str(i),'phase':str(i)} for i in [0,2,4,6]]
        jobs=H.segments(keys,8,True)
        self.assertEqual([j['slots'] for j in jobs],[[1],[3],[5],[7]])
        self.assertEqual(jobs[-1]['end'],'0');self.assertEqual(jobs[-1]['to'],8)
        self.assertEqual([j['raw_indices'] for j in jobs],[[2]]*4)

    def test_action_semantics_are_metadata_not_full_action_prompts(self):
        self.c['action']='violent-battleaxe-attack'
        self.c['directions'][0]['keys'][1]['phase']='attack-windup'
        self.prepare();job=P.load(self.root/'evidence/jobs.json')[0]
        body=H.payload(self.root,job)
        self.assertNotIn('battleaxe',body['action']);self.assertNotIn('windup',body['action'])
        self.assertEqual(job['end_phase'],'attack-windup')

    def test_legacy_live_transport_also_requires_both_endpoints(self):
        c={'schema_version':1,'model':'v3','description':'fixture','action':'fixture','image_size':[64,64],'frame_count':4,
           'frame_ms':100,'loop':True,'pivot':[32,3],'ppu':'fixture','reference_policy':'prefixed',
           'directions':[{'direction':'south','reference':'0.png'}], 'budget':{'usd':1,'max_jobs':1,'reserve_usd_per_job':.05}}
        p=self.base/'legacy.json';P.save(p,c);root=self.base/'legacy';P.prepare(p,root)
        with self.assertRaisesRegex(ValueError,'both authored endpoint'):P.submit(root,self.api,'south')
        self.assertFalse(self.api.posts)

    def test_one_shot_requires_final_authored_pose(self):
        with self.assertRaisesRegex(ValueError,'final key'):H.segments([{'frame':0,'path':'0','phase':'0'},{'frame':2,'path':'2','phase':'2'}],5,False)

    def test_large_unconstrained_gap_requires_more_key_poses(self):
        with self.assertRaisesRegex(ValueError,'meaningful action key'):H.segments([{'frame':0,'path':'0','phase':'0'},{'frame':20,'path':'20','phase':'20'}],21,False)

    def test_get_failure_resumes_same_job_without_post_retry(self):
        self.prepare();self.api.get_failure=True
        with self.assertRaises(P.APIError):H.run(self.root,self.api)
        self.assertEqual(len(self.api.posts),1);self.assertEqual(P.load(self.budget)['jobs'][0]['status'],'processing')
        self.api.get_failure=False;H.run(self.root,self.api)
        self.assertEqual(len(self.api.posts),1);H.assemble(self.root)

    def test_ambiguous_post_is_not_retried(self):
        self.prepare();self.api.uncertain=True
        with self.assertRaises(P.APIError):H.run(self.root,self.api)
        with self.assertRaisesRegex(ValueError,'Ambiguous POST'):H.run(self.root,self.api)
        self.assertEqual(len(self.api.posts),1)

    def test_all_actions_share_one_spending_limit(self):
        self.prepare();ledger=P.load(self.budget);ledger['usd']=.06;P.save(self.budget,ledger)
        H.run(self.root,self.api)
        other=self.base/'other';H.prepare(self.path,other)
        with self.assertRaisesRegex(ValueError,'Shared USD budget'):H.run(other,self.api)
        self.assertEqual(len(self.api.posts),1)

    def test_prepared_key_tampering_stops_before_post(self):
        self.prepare();frame(2).save(self.root/'inputs/south/00.png')
        with self.assertRaisesRegex(ValueError,'input changed'):H.run(self.root,self.api)
        self.assertFalse(self.api.posts)

    def test_native_provider_edit_is_detected_before_packaging(self):
        self.prepare();H.run(self.root,self.api)
        frame(0).save(self.root/'evidence/api/south-000-004/raw/frame-02.png')
        with self.assertRaisesRegex(ValueError,'Provider output changed'):H.assemble(self.root)

    def test_procedural_frames_need_no_budget_or_api(self):
        self.c.update(route='procedural',frame_count=4,frame_ms=100)
        self.c.pop('budget_file');self.c['directions']=[{'direction':'south','frames':['0.png','1.png','2.png','3.png']}]
        self.prepare();H.assemble(self.root)
        with self.assertRaisesRegex(ValueError,'never submit'):H.run(self.root,self.api)
        self.assertFalse(self.api.posts)
        self.assertEqual(P.load(self.root/'evidence/audit.json')['directions'][0]['inbetweens'],0)

    def test_closed_budget_cannot_submit(self):
        self.prepare();ledger=P.load(self.budget);ledger['status']='closed';P.save(self.budget,ledger)
        with self.assertRaisesRegex(ValueError,'closed'):H.run(self.root,self.api)
        self.assertFalse(self.api.posts)

    def test_partial_row_is_explicit_and_does_not_approve_missing_views(self):
        other=json.loads(json.dumps(self.c['directions'][0]));other['direction']='east';self.c['directions'].append(other)
        self.prepare();H.run(self.root,self.api,max_new_jobs=1);H.assemble(self.root,['south'])
        m=P.load(self.root/'generated/manifest.json');self.assertFalse(m['complete'])
        self.assertEqual(m['requested_direction_order'],['south','east']);self.assertEqual(m['direction_order'],['south'])
        self.assertFalse(P.load(self.root/'evidence/audit.json')['complete'])
        with self.assertRaisesRegex(ValueError,'Missing inbetweens'):H.assemble(self.root)

    def test_partial_output_rejects_unknown_view(self):
        self.prepare()
        with self.assertRaisesRegex(ValueError,'Unknown partial'):H.assemble(self.root,['east'])

    def test_opaque_matte_input_is_rejected_before_prepare(self):
        Image.new('RGBA',(64,64),(20,20,20,255)).save(self.base/'0.png')
        with self.assertRaisesRegex(ValueError,'Transparent binary'):self.prepare()
        self.assertFalse(self.root.exists());self.assertFalse(self.api.posts)

    def test_unused_processed_reference_can_be_opaque_without_replacing_keys(self):
        original=self.api.call
        def call(method,endpoint,body=None):
            result=original(method,endpoint,body)
            if endpoint.startswith('/background-jobs/'):
                opaque=Image.new('RGBA',(64,64),(30,30,30,255))
                result['last_response']['images'][0]['base64']=base64.b64encode(P.png(opaque)).decode()
            return result
        self.api.call=call;self.prepare();H.run(self.root,self.api);H.assemble(self.root)
        self.assertEqual((self.root/'generated/south/frame-00.png').read_bytes(),(self.base/'0.png').read_bytes())

    def test_large_canvas_can_raise_the_shared_reservation_floor(self):
        self.c['reserve_usd_per_job']=.5;self.prepare();d=P.load(self.budget);d['usd']=.2;P.save(self.budget,d)
        with self.assertRaisesRegex(ValueError,'Shared USD budget'):H.run(self.root,self.api)
        self.assertFalse(self.api.posts)

    def test_closed_action_still_resumes_accepted_job_without_new_posts(self):
        other=json.loads(json.dumps(self.c['directions'][0]));other['direction']='east';self.c['directions'].append(other)
        self.prepare();self.api.get_failure=True
        with self.assertRaises(P.APIError):H.run(self.root,self.api)
        c=P.load(self.root/'contract.json');c['submission_closed']=True;P.save(self.root/'contract.json',c)
        self.api.get_failure=False
        with self.assertRaisesRegex(ValueError,'closed for new'):H.run(self.root,self.api)
        self.assertEqual(len(self.api.posts),1);self.assertEqual(P.load(self.budget)['jobs'][0]['status'],'completed')


if __name__=='__main__':unittest.main()
