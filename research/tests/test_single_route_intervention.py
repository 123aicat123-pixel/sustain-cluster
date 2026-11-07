"""Single-perturbation contract tests; no future state or carbon labels."""
import unittest
from types import SimpleNamespace as NS

from research.single_route_intervention import first_batch_probe


def task(name, cores, duration, gpu=0):
    return NS(job_name=name,cores_req=cores,duration=duration,
              gpu_req=gpu,mem_req=0,origin_dc_id=1)


def dc(dc_id, ci, cores=10):
    return NS(dc_id=dc_id,total_cores=cores,total_gpus=2,
              total_mem_GB=100,
              get_current_carbon_intensity=lambda norm=False:ci)


class InterventionTest(unittest.TestCase):
    def setUp(self):
        self.tasks=[task("A",3,10),task("B",4,20)]
        self.dcs=[dc(1,250),dc(2,100),dc(3,500)]
        self.original=[1,1]

    def test_one_action_only_and_extreme_choices(self):
        ctrl,c0=first_batch_probe(self.tasks,self.original,self.dcs,arm="control")
        low,c1=first_batch_probe(self.tasks,self.original,self.dcs,arm="low_ci")
        high,c2=first_batch_probe(self.tasks,self.original,self.dcs,arm="high_ci")
        self.assertEqual(ctrl,self.original)
        self.assertEqual(low,[1,2])
        self.assertEqual(high,[1,3])
        self.assertEqual([c0["task_name"],c1["task_name"],c2["task_name"]],
                         ["B"]*3)
        self.assertEqual((c1["control_dc_id"],c2["control_dc_id"]),(1,1))
        self.assertEqual((c1["selected_dc_id"],c2["selected_dc_id"]),(2,3))
        self.assertEqual(self.original,[1,1])

    def test_capacity_exclusion(self):
        dcs=[dc(1,300),dc(2,100,cores=2),dc(3,450,cores=10)]
        actions,metadata=first_batch_probe(self.tasks,self.original,dcs,arm="low_ci")
        self.assertEqual(actions,[1,3])
        self.assertEqual(metadata["selected_dc_id"],3)

    def test_tie_is_stable(self):
        dcs=[dc(1,250),dc(7,100),dc(3,100)]
        actions,metadata=first_batch_probe(self.tasks,self.original,dcs,arm="low_ci")
        self.assertEqual(actions,[1,3])
        self.assertEqual(metadata["selected_dc_id"],3)

    def test_unrouteable_task_returns_no_metadata(self):
        result,meta=first_batch_probe([task("A",20,10)], [1],
                                      [dc(1,200,cores=20),dc(2,50,cores=10)],arm="high_ci")
        self.assertEqual((result,meta),([1],None))

    def test_empty_and_invalid(self):
        self.assertEqual(first_batch_probe([],[],self.dcs,arm="control"),([],None))
        with self.assertRaises(ValueError):
            first_batch_probe(self.tasks,self.original,self.dcs,arm="impossible")
        with self.assertRaises(AssertionError):
            first_batch_probe(self.tasks,[1],self.dcs,arm="control")


if __name__=="__main__":
    unittest.main()
