from rediz.client import Rediz
import json, random, time
from rediz.rediz_test_config import REDIZ_TEST_CONFIG



def dump(obj,name="garbage.json"): # Debugging
    json.dump(obj,open("tmp_garbage.json","w"))

def test_delete_simple():
    rdz = Rediz(**REDIZ_TEST_CONFIG)
    title = rdz.random_title()
    assert rdz.set(value="42",**title)
    dump(title)
    name, write_key = title["name"], title["write_key"]
    assert rdz.get(name)=="42"
    rdz._delete_implementation(names=[name])
    assert rdz.get(name) is None

def test_expire():
    rdz = Rediz(**REDIZ_TEST_CONFIG)
    title = rdz.random_title()
    assert rdz.set(value="42",**title)
    name, write_key = title["name"], title["write_key"]
    rdz.client.expire(name=title["name"],time=0)
    import time
    time.sleep(0.1)
    name, write_key = title["name"], title["write_key"]
    assert rdz.get(name) is None
    assert rdz.client.sismember(name=rdz._NAMES, value=name)
    rdz._delete_implementation(names=[name])

def test_run_admin_garbage_collection():
    rdz = Rediz(**REDIZ_TEST_CONFIG)
    rdz.admin_garbage_collection()
    report = rdz.card()
    if False:
        dump(report)

def test_admin_garbage_collection(num=100):
    rdz = Rediz(**REDIZ_TEST_CONFIG)
    original_num = rdz.card()
    names      = [ rdz.random_name() for _ in range(num) ]
    write_keys = [ rdz.random_key() for _ in range(num) ]
    values = ["from test_admin_garbage_collection" for _ in write_keys ]
    assert rdz.mset(names=names,write_keys=write_keys,values=values)==len(values)
    expire_pipe = rdz.client.pipeline()
    for name in names:
        expire_pipe.expire(name=name,time=0)
    expire_pipe.execute()
    time.sleep(0.1)

    remaining = list()
    for iter_no in range(5):
        rdz.admin_garbage_collection( fraction=0.01 )
        remaining.append( rdz.card() )

    final_num = rdz.card()
    rdz._delete_implementation(*names)

def test_find_orphans_low_cardinality_test(num=20):

    rdz = Rediz(**REDIZ_TEST_CONFIG)

    original_num = rdz.card()
    if original_num<10000:
        # This test won't ultimately scale as it calls smembers
        original_set = rdz.client.smembers(rdz._NAMES)
        for k in [5,20,400]:
            some = rdz.client.srandmember(rdz._NAMES, k)
            some_unique = list(set(some))
            assert all( s in original_set for s in some )
            assert len(some_unique)<=original_num

        # Create some data with short ttl
        names = [ rdz.random_name() for _ in range(num) ]
        write_keys = [ rdz.random_key() for _ in range(num) ]
        value  = "a string to store"
        values = [value for _ in write_keys ]
        title = rdz.mset(names=names,write_keys=write_keys,values=values)
        assert rdz.client.exists(*names)==len(names), "Names were not created as expected."
        for name in names:
            rdz.client.expire(name=name,time=5*60)

        expiring_names = [ n for n in names if random.choice(['expired','living'])=='expired' ]
        for expiring_name in expiring_names:
            rdz.client.expire(name=expiring_name,time=0)
        time.sleep(0.1)
        assert rdz.client.exists(*expiring_names)==0, "Names did not expire as expected"

        some_orphans = rdz._randomly_find_orphans(num=50)

        # Clean up most
        almost_all_orphans = rdz._randomly_find_orphans(num=10*num)
        if almost_all_orphans:
            rdz._delete_implementation(*almost_all_orphans)

        # Clean up scraps
        rdz._delete_implementation(*names)

        final_num = rdz.card()
        final_set = rdz.client.smembers(rdz._NAMES)
        set_diff_1  = final_set.difference(original_set)
        set_diff_2  = original_set.difference(final_set)

        if False:
            dump({"original_num":original_num,
                  "num_added":len(names),
                  "final_num":final_num,
                  "num_orphans":len(some_orphans),
                  "num_orphans_wider_search":len(almost_all_orphans),
                  "set_diff_1":list(set_diff_1),
                  "set_diff_2":list(set_diff_2)})
