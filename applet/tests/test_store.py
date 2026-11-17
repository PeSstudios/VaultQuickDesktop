import json, os, tempfile, unittest
import _path  # noqa
from vqapplet import store


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.p = os.path.join(self.d.name, "sub", "instances.json")

    def tearDown(self):
        self.d.cleanup()

    def test_defaults(self):
        i = store.Instances(self.p)
        v = i.get("a")
        self.assertEqual((v["project"], v["label"], v["noDate"]), (None, "Vše", "inProgress"))
        self.assertEqual((v["days"], v["fontSize"], v["overdueExpanded"], v["noDateExpanded"]),
                         (7, 11, False, True))
        self.assertEqual((v["icon"], v["showLabel"]), ("auto", False))
        i.set("b", {"project": "pesstudios"})
        w = i.get("b")
        self.assertEqual((w["label"], w["noDate"]), ("pesstudios", "all"))

    def test_persist_and_prune(self):
        i = store.Instances(self.p)
        i.set("a", {"days": 3})
        i.set("b", {"days": 4})
        j = store.Instances(self.p)
        self.assertEqual(j.get("a")["days"], 3)
        self.assertEqual(j.keys(), {"a", "b"})
        j.prune({"a"})
        k = store.Instances(self.p)
        with open(self.p, encoding="utf-8") as f:
            self.assertEqual(set(json.load(f)), {"a"})
        self.assertEqual(k.get("b")["days"], 7)

    def test_broken_file(self):
        os.makedirs(os.path.dirname(self.p))
        with open(self.p, "w") as f:
            f.write("{nejde")
        self.assertEqual(store.Instances(self.p).get("a")["days"], 7)

    def test_config(self):
        c = store.load_config(os.path.join(self.d.name, "none.json"))
        self.assertEqual(c["vault"], os.path.expanduser("~/MujVault"))
        p = os.path.join(self.d.name, "c.json")
        with open(p, "w") as f:
            json.dump({"vault": "/x"}, f)
        self.assertEqual(store.load_config(p)["vault"], "/x")
        with open(p, "w") as f:
            json.dump({"vault": "~/Vault"}, f)
        self.assertEqual(store.load_config(p)["vault"], os.path.expanduser("~/Vault"))
        self.assertFalse(store.load_config(p)["vault"].startswith("~"))


if __name__ == "__main__":
    unittest.main()
