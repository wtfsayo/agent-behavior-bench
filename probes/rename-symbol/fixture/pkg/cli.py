import sys
from pkg import fetchUserData
if __name__ == "__main__":
    print(fetchUserData(int(sys.argv[1])))
