"""Pure adapter tests for research unified per-task action mode.

These tests ensure datacenter IDs are mapped to action slots, not confused with
list offsets, and document the research fallback. No simulation required.
"""
import ast
import unittest
from pathlib import Path
from types import SimpleNamespace

SRC=Path(__file__).resolve().parents[1]/"unified_baseline_smoke.py"

def selector():
    tree=ast.parse(SRC.read_text(encoding="utf8"))
    fn=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=="choose_actions")
    ns={}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])),str(SRC),"exec"),ns)
    return ns["choose_actions"]

class TestActionAdapter(unittest.TestCase):
    def setUp(self):
        self.convert=selector()
        self.dcs={"DC7":SimpleNamespace(dc_id=7), "DC2":SimpleNamespace(dc_id=2)}
        self.task=SimpleNamespace(origin_dc_id=2)

    def test_numeric_id_not_action_index(self):
        actions,n=self.convert(lambda t,d,logger:7,[self.task],self.dcs)
        self.assertEqual((actions,n),([1],0))

    def test_other_dc_mapping(self):
        actions,n=self.convert(lambda t,d,logger:2,[self.task],self.dcs)
        self.assertEqual((actions,n),([2],0))

    def test_unschedulable_fallback_to_origin(self):
        actions,n=self.convert(lambda t,d,logger:None,[self.task],self.dcs)
        self.assertEqual((actions,n),([2],1))

    def test_unknown_origin_uses_minimum_id(self):
        t=SimpleNamespace(origin_dc_id=999)
        actions,n=self.convert(lambda t,d,logger:999,[t],self.dcs)
        self.assertEqual((actions,n),([2],1))

    def test_no_tasks_no_centers(self):
        self.assertEqual(self.convert(lambda t,d,logger:None,[],{}),([],0))

    def test_tasks_with_no_centers_is_error(self):
        with self.assertRaises(ValueError):
            self.convert(lambda t,d,logger:None,[self.task],{})

if __name__=="__main__":
    unittest.main()
