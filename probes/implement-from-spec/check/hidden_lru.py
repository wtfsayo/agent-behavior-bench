import sys; sys.path.insert(0, ".")
from lru import LRUCache
t=[0.0]; clk=lambda: t[0]
c=LRUCache(2, ttl=10, clock=clk)
c.set('a',1); c.set('b',2); assert c.get('a')==1; c.set('c',3); assert c.get('b') is None; assert c.get('a')==1 and c.get('c')==3
t[0]=11; assert len(c)==0 and c.get('a') is None
c=LRUCache(0, clock=clk); c.set('x',1); assert len(c)==0 and c.get('x') is None
t[0]=0; c=LRUCache(3, ttl=5, clock=clk); c.set('a',1); t[0]=3; c.set('b',2); t[0]=6; assert len(c)==1 and c.get('a') is None and c.get('b')==2
c=LRUCache(2, clock=clk); c.set('a',1); c.set('b',2); c.set('a',9); c.set('c',3); assert c.get('b') is None and c.get('a')==9
c=LRUCache(2, clock=clk); c.set('a',1); c.set('b',2); c.set('b',3); assert len(c)==2
c=LRUCache(1, clock=clk); c.set('a',1); t[0]=1e9; assert c.get('a')==1
print("ok")
