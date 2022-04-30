
import os
import os.path
import time
import hmac
import uuid
import hashlib
from flask import current_app
from nacl.encoding import HexEncoder
from nacl.signing import SigningKey, VerifyKey
import error


def cloud_key() -> SigningKey:
    try:
        if 'CLOUD_KEY' in current_app.config:
            return current_app.config['CLOUD_KEY']
    except RuntimeError:
        pass
    try:
        if not os.path.isfile('cloud.key'):
            print('warning: generated cloud key')
            key = SigningKey.generate()
            with open('cloud.key', 'wb') as f:
                f.write(key.encode())
            with open('cloud.pub', 'wb') as f:
                f.write(key.verify_key.encode())
        with open('cloud.key', 'rb') as f:
            return SigningKey(f.read())
    except:
        print('fatal: Error loading CLOUD_KEY')
        exit(2)


def sign(data: str) -> str:
    return cloud_key().sign(data.encode(), encoder=HexEncoder).signature


def verify(data: str, sig: str, pub: str = None) -> bool:
    if pub:
        verify_key = VerifyKey(pub, encoder=HexEncoder)
    else:
        verify_key = cloud_key().verify_key
    try:
        verify_key.verify(data.encode(), HexEncoder().decode(sig))
        return True
    except:
        return False


def hash_file(file: str) -> str:
    h = hashlib.sha256()
    with open(file, 'rb') as f:
        while True:
            chunk = f.read(h.block_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def sign_file(file: str) -> str:
    return sign(hash_file(file))


def sign_device(uuid: uuid.UUID):
    device_key = SigningKey().generate()
    device_pubkey = device_key.verify_key.encode(HexEncoder)
    device_cert = sign(device_pubkey+str(uuid))
    return device_key.encode(), device_pubkey+':'+device_cert


def timestamp(_time: int = 0) -> str:
    t = str(int(_time if _time else time.time()))
    sig = hmac.new(current_app.config['SECRET_KEY'].encode(
    ), t.encode(), hashlib.sha1).hexdigest()
    return t+':'+sig


def check_ticket(ticket: str, uuid: uuid.UUID) -> None:
    try:
        t, tsig, sig, pubkey, cert = ticket.split(':')
        ts = t+':'+tsig
        if timestamp(t) != ts:
            raise error.NotLoggedIn('Invalid timestamp in device ticket')
        if t+current_app.config['TICKET_LIFETIME'] < time.time():
            raise error.NotLoggedIn('Timestamp expired')
        if not verify(ts, sig, pubkey):
            raise error.NotLoggedIn('Invalid timestamp signature')
        if not verify(pubkey+str(uuid), cert):
            raise error.NotLoggedIn('Invalid pubkey')
    except error.DSDException as e:
        raise e
    except Exception:
        raise error.NotLoggedIn('Invalid device ticket')


def check_file(file: str, sig: str, uuid: uuid.UUID) -> None:
    try:
        sig, pubkey, cert = sig.split(':')
        hash = hash_file(file)
        if not verify(hash, sig, pubkey):
            raise error.APISyntaxError('Invalid file signautre')
        if not verify(pubkey+str(uuid), cert):
            raise error.APISyntaxError('Invalid file pubkey')
    except error.DSDException as e:
        raise e
    except Exception:
        raise error.APISyntaxError('Invalid signature')
