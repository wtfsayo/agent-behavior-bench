from dataclasses import dataclass
@dataclass
class UserRecord:
    id: int
    name: str
def fetchUserData(uid: int) -> UserRecord:
    """Look up a user. (fake)"""
    return UserRecord(uid, f"user{uid}")
