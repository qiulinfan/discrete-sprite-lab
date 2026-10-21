#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow>=11,<14"]
# ///
"""Offline transport, budget, integrity and review regression tests. MIT License."""
import base64
import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/pixellab_actions.py"
SPEC = importlib.util.spec_from_file_location("pixellab_actions", SCRIPT)
P = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P)


class FakeAPI:
    """Documented async response shapes, with no external network or credentials."""
    def __init__(self):
        self.posts = 0
        self.jobs = {}
        self.reject = None
        self.credits = 10.0
        self.trial = 40.0

    def call(self, method, endpoint, body=None):
        if method == "GET" and endpoint == "/balance":
            return {"credits":{"type":"usd","usd":self.credits},"subscription":{"type":"generations","status":"trial","plan":None,"generations":self.trial,"total":40.0}}
        if method == "POST":
            self.posts += 1
            if self.reject:
                raise P.APIError("synthetic submission failure", self.reject if type(self.reject) is int else None)
            number = str(self.posts)
            first = P.rgba(base64.b64decode(body["first_frame"]["base64"]))
            processed = first.copy()
            processed.putpixel((24,12),(90,70,50,255))
            frames = [processed]
            for i in range(body["frame_count"]):
                image = first.copy()
                image.putpixel((28+i,42),(150+i,80,30,255))
                frames.append(image)
            self.jobs[number] = {"id":number,"created_at":"2026-10-10T00:00:00Z","status":"completed","usage":{"type":"generations","generations":1},"last_response":{"images":[{"type":"base64","base64":base64.b64encode(P.png(im)).decode()} for im in frames],"usage":{"type":"generations","generations":1,"usd":0,"cost_if_paid":0.025}}}
            self.trial -= 1
            return {"background_job_id":number,"status":"processing"}
        return copy.deepcopy(self.jobs[endpoint.rsplit("/",1)[-1]])


class PixelLabActionsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.root = self.home / "output"
        image=Image.new("RGBA",(64,64))
        draw=ImageDraw.Draw(image)
        draw.rectangle((24,12,39,52),fill=(100,60,30,255))
        image.save(self.home/"reference.png")
        self.contract={"schema_version":1,"model":"v3","description":"fixture reference","action":"Walk in place.","directions":[{"direction":"south","reference":"reference.png","last_frame":"reference.png"},{"direction":"east","reference":"reference.png","last_frame":"reference.png"}],"image_size":[64,64],"frame_count":6,"frame_ms":120,"slow_multiplier":3,"loop":True,"pivot":[32,3],"ppu":"fixture family","palette_max_colors":None,"reference_policy":"prefixed","budget":{"usd":1,"max_jobs":4,"reserve_usd_per_job":0.25}}
        self.path=self.home/"request.json"
        P.save(self.path,self.contract)
        self.api=FakeAPI()

    def tearDown(self):
        self.temp.cleanup()

    def generate(self):
        P.prepare(self.path,self.root)
        P.run(self.root,self.api)
        return P.package(self.root)

    def review(self,manifest):
        result={"sheet_sha256":manifest["sheet_sha256"],"frame_hashes":{f"{f['direction']}/{f['index']}":f["rgba_sha256"] for f in manifest["frames"]},"frame_ms":120,"slow_multiplier":3,"loop":True,"direction_order":manifest["direction_order"],"authority":"fixture only; not a real art review","individual_frame_review":True,"normal_and_slow_review":True,"verdict":"candidate-with-warnings","findings":{"south":"synthetic fixture","east":"synthetic fixture"},"warnings":["not real generated art"]}
        path=self.home/"review.json";P.save(path,result)
        return path,result

    def test_sequential_completion_and_resume_does_not_post_again(self):
        manifest,audit=self.generate()
        self.assertEqual(len(manifest["frames"]),12)
        self.assertTrue(audit["hard_pass"])
        self.assertEqual(audit["visual_verdict"],"awaiting-visual-review")
        P.run(self.root,self.api)
        self.assertEqual(self.api.posts,2)
        cost=P.load(self.root/"api/cost-ledger.json")
        self.assertEqual(cost["actual_usd_balance_delta"],0)
        self.assertEqual(cost["subscription_generations_delta"],2)
        self.assertAlmostEqual(cost["cost_if_paid_usd_total"],0.05)

    def test_processed_prefix_is_retained_and_not_assumed_identical(self):
        self.generate()
        decoded=P.load(self.root/"api/jobs/south/attempt-01/decode.json")
        self.assertEqual(decoded["raw_count"],7)
        self.assertEqual(decoded["selected_raw_indices"],list(range(1,7)))
        self.assertFalse(decoded["prefixed_reference_observation"]["exact_rgba_match"])
        self.assertEqual(len(list((self.root/"api/jobs/south/attempt-01/raw").glob("*.png"))),7)

    def test_budget_and_credit_reserve_prevent_any_post(self):
        P.prepare(self.path,self.root)
        self.api.credits=0.01
        with self.assertRaisesRegex(ValueError,"credit reserve"):
            P.run(self.root,self.api)
        self.assertEqual(self.api.posts,0)

    def test_account_debit_guard_blocks_next_submission(self):
        P.prepare(self.path,self.root)
        P.save(self.root/"api/balance-initial.json",self.api.call("GET","/balance"))
        self.api.credits=9.2
        with self.assertRaisesRegex(ValueError,"USD budget"):
            P.run(self.root,self.api)
        self.assertEqual(self.api.posts,0)

    def test_uncertain_post_cannot_be_blindly_retried(self):
        P.prepare(self.path,self.root)
        self.api.reject="uncertain"
        with self.assertRaises(P.APIError):P.run(self.root,self.api)
        self.assertEqual(P.load(self.root/"state.json")["jobs"][0]["status"],"post-uncertain")
        self.api.reject=None
        with self.assertRaisesRegex(ValueError,"uncertain"):
            P.run(self.root,self.api)
        self.assertEqual(self.api.posts,1)

    def test_rejected_post_requires_explicit_bounded_retry(self):
        P.prepare(self.path,self.root)
        self.api.reject=429
        with self.assertRaises(P.APIError):P.run(self.root,self.api)
        self.api.reject=None
        with self.assertRaisesRegex(ValueError,"explicit"):
            P.run(self.root,self.api)
        P.run(self.root,self.api,retry_direction="south")
        P.run(self.root,self.api)
        self.assertEqual(self.api.posts,3)

    def test_reference_tamper_is_detected_before_post(self):
        P.prepare(self.path,self.root)
        item=P.load(self.root/"contract.json")["directions"][0]
        (self.root/item["reference"]).write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError,"Reference changed"):
            P.run(self.root,self.api)
        self.assertEqual(self.api.posts,0)

    def test_unexpected_count_keeps_raw_and_marks_artifact_failure(self):
        P.prepare(self.path,self.root)
        P.save(self.root/"api/balance-initial.json",self.api.call("GET","/balance"))
        job=P.submit(self.root,self.api,"south")
        self.api.jobs[job["job_id"]]["last_response"]["images"].pop()
        with self.assertRaisesRegex(ValueError,"Unexpected frame count"):
            P.poll_job(self.root,self.api,job)
        self.assertEqual(P.load(self.root/"state.json")["jobs"][0]["status"],"artifact-failed")
        self.assertEqual(len(list((self.root/"api/jobs/south/attempt-01/raw").glob("*.png"))),6)

    def test_palette_cap_and_positive_review_do_not_override_hard_failure(self):
        manifest,_=self.generate()
        contract=P.load(self.root/"contract.json");contract["palette_max_colors"]=1;P.save(self.root/"contract.json",contract)
        path,_=self.review(manifest)
        _,audit=P.package(self.root,path)
        self.assertFalse(audit["hard_pass"])
        self.assertEqual(audit["visual_verdict"],"technical-fail")

    def test_review_is_invalidated_by_changed_timing(self):
        manifest,_=self.generate()
        path,_=self.review(manifest)
        P.package(self.root,path)
        contract=P.load(self.root/"contract.json");contract["frame_ms"]=140;P.save(self.root/"contract.json",contract)
        with self.assertRaisesRegex(ValueError,"timing"):
            P.package(self.root,path)
        self.assertEqual(P.load(self.root/"generated/audit.json")["visual_verdict"],"awaiting-visual-review")

    def test_visual_review_needs_all_direction_findings(self):
        manifest,_=self.generate()
        path,review=self.review(manifest);review["findings"].pop("east");P.save(path,review)
        with self.assertRaisesRegex(ValueError,"every direction"):
            P.package(self.root,path)

    def test_raw_and_selected_tampering_cannot_rewrite_provider_output(self):
        self.generate()
        base=self.root/"api/jobs/south/attempt-01"
        altered=Image.new("RGBA",(64,64),(1,2,3,255))
        altered.save(base/"raw/frame-01.png");altered.save(base/"frames/frame-00.png")
        with self.assertRaisesRegex(ValueError,"raw provider PNG changed"):
            P.package(self.root)

    def test_replay_is_offline_and_rejects_reference_mismatch(self):
        self.generate()
        recordings=self.home/"recordings"
        for job in P.load(self.root/"state.json")["jobs"]:
            source=P.attempt_path(self.root,job)
            P.save(recordings/job["direction"]/"request.json",P.load(source/"request.json"))
            P.save(recordings/job["direction"]/"job-latest.json",P.load(source/"result.json"))
        replay_root=self.home/"replay"
        with patch.object(P.PixelLab,"call",side_effect=AssertionError("network forbidden")):
            P.replay(self.path,recordings,replay_root)
            manifest,audit=P.package(replay_root)
            self.assertTrue(audit["hard_pass"])
        with self.assertRaises(ValueError):
            P.submit(replay_root,self.api,"south")
        old=P.load(recordings/"south/request.json")
        old["payload"]["first_frame"]["base64"]=base64.b64encode(P.png(Image.new("RGBA",(64,64)))).decode()
        P.save(recordings/"south/request.json",old)
        with self.assertRaisesRegex(ValueError,"reference does not match"):
            P.replay(self.path,recordings,self.home/"bad-replay")

    def test_one_shot_apng_plays_once_and_retains_timing(self):
        self.contract["loop"]=False;self.contract["frame_ms"]=123;P.save(self.path,self.contract)
        self.generate()
        with Image.open(self.root/"evidence/loops/south-normal.png") as image:
            self.assertEqual(image.info["loop"],1)
            self.assertEqual(image.n_frames,6)
            self.assertEqual(image.info["duration"],123)

    def test_provider_partial_alpha_is_a_hard_failure(self):
        self.contract["directions"]=self.contract["directions"][:1];P.save(self.path,self.contract)
        P.prepare(self.path,self.root)
        P.save(self.root/"api/balance-initial.json",self.api.call("GET","/balance"))
        job=P.submit(self.root,self.api,"south")
        items=self.api.jobs[job["job_id"]]["last_response"]["images"]
        frame=P.rgba(base64.b64decode(items[1]["base64"]));frame.putpixel((1,1),(50,40,30,128))
        items[1]["base64"]=base64.b64encode(P.png(frame)).decode()
        P.poll_job(self.root,self.api,job)
        _,audit=P.package(self.root)
        self.assertFalse(audit["hard_pass"])
        self.assertEqual(audit["visual_verdict"],"technical-fail")

    def test_transparent_rgb_changes_do_not_hide_duplicate_visible_phases(self):
        self.contract["directions"]=self.contract["directions"][:1];P.save(self.path,self.contract)
        P.prepare(self.path,self.root)
        P.save(self.root/"api/balance-initial.json",self.api.call("GET","/balance"))
        job=P.submit(self.root,self.api,"south")
        items=self.api.jobs[job["job_id"]]["last_response"]["images"]
        frame=P.rgba(base64.b64decode(items[1]["base64"]));frame.putpixel((0,0),(230,40,20,0))
        items[2]["base64"]=base64.b64encode(P.png(frame)).decode()
        P.poll_job(self.root,self.api,job)
        _,audit=P.package(self.root)
        self.assertFalse(audit["hard_pass"])

    def test_contract_rejects_invalid_v3_count_and_unknown_inline_fields(self):
        for count in (3,5,18):
            bad=copy.deepcopy(self.contract);bad["frame_count"]=count
            with self.assertRaises(ValueError):P.validate_contract(bad)
        bad=copy.deepcopy(self.contract);bad["headers"]={"Authorization":"not serialized"}
        with self.assertRaisesRegex(ValueError,"Unknown contract"):
            P.validate_contract(bad)


if __name__=="__main__":
    unittest.main()
