import m1,m2,m3,m4,m5,m6
def test():
    for i,m in enumerate([m1,m2,m3,m4,m5,m6],1):
        assert getattr(m,f"f{i}")(10)==10+i
