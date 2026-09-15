import requests

def fetch(url):
    r = requests.get(url)
    return r.json()
