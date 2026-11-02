"""M4a §0/§2 — config generatori: snapshot (deterministik), qator in'ektsiyasi, XML escape, maskalash."""
from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from app.services import prov_render as r
from app.services.prov_render import CommonCtx, DeviceCtx, KeySpec, masked, render, render_yealink_common

CTX = DeviceCtx(mac="805ec0aabbcc", number="101", display_name="Ali", sip_user="t1-101", password="Pw1",
                server_host="pbx.local", keys=(KeySpec(1, "blf", "102", "Vali"),))

YEALINK = """#!version:1.0.0.1
lang.gui = English
lang.wui = English
local_time.time_zone = +5
local_time.ntp_server1 = pool.ntp.org
local_time.summer_time = 0
static.auto_provision.power_on = 1
account.1.enable = 1
account.1.label = 101
account.1.display_name = Ali
account.1.auth_name = t1-101
account.1.user_name = t1-101
account.1.password = Pw1
account.1.sip_server.1.address = pbx.local
account.1.sip_server.1.port = 5060
account.1.sip_server.1.transport_type = 0
voice_mail.number.1 = *97
linekey.1.type = 16
linekey.1.line = 1
linekey.1.value = 102
linekey.1.label = Vali
"""

GRANDSTREAM = """<?xml version="1.0" encoding="UTF-8"?>
<gs_provision version="1">
  <mac>805ec0aabbcc</mac>
  <config version="1">
    <P271>1</P271>
    <P270>101</P270>
    <P47>pbx.local:5060</P47>
    <P35>t1-101</P35>
    <P36>t1-101</P36>
    <P34>Pw1</P34>
    <P3>Ali</P3>
    <P33>*97</P33>
    <P130>0</P130>
    <P64>customize</P64>
    <P246>&lt;+05&gt;-5</P246>
    <P30>pool.ntp.org</P30>
    <P1362>en</P1362>
  </config>
</gs_provision>
"""

FANVIL = """<<VOIP CONFIG FILE>>Version:2.0000000000

<GLOBAL CONFIG MODULE>
Enable SNTP             :1
SNTP Server             :pool.ntp.org
Time Zone               :300
Language                :en

<SIP CONFIG MODULE>
SIP1 Phone Number       :t1-101
SIP1 Display Name       :Ali
SIP1 Register Addr      :pbx.local
SIP1 Register Port      :5060
SIP1 Register User      :t1-101
SIP1 Register Pswd      :Pw1
SIP1 Transport          :0
SIP1 Enable Reg         :1
SIP1 VoiceMail Number   :*97

<DSS CONFIG MODULE>
Fkey1 Type              :1
Fkey1 Value             :102@1/b
Fkey1 Title             :Vali
"""


@pytest.mark.parametrize(("vendor", "filename", "expected"), [
    ("yealink", "805ec0aabbcc.cfg", YEALINK),
    ("grandstream", "cfg805ec0aabbcc.xml", GRANDSTREAM),
    ("fanvil", "805ec0aabbcc.cfg", FANVIL),
])
def test_snapshot(vendor: str, filename: str, expected: str) -> None:
    name, body = render(vendor, "ANY", CTX)
    assert name == filename
    assert body.decode() == expected
    assert render(vendor, "ANY", CTX) == (name, body)  # deterministik


def test_yealink_common_has_no_secrets() -> None:
    body = render_yealink_common(CommonCtx(language="ru", timezone="Asia/Kolkata", ntp_server="ntp.uz")).decode()
    assert body == ("#!version:1.0.0.1\nlang.gui = Russian\nlang.wui = Russian\nlocal_time.time_zone = +5:30\n"
                    "local_time.ntp_server1 = ntp.uz\nlocal_time.summer_time = 0\nstatic.auto_provision.power_on = 1\n")
    assert "password" not in body and "account" not in body


def test_admin_password_lines() -> None:
    ctx = DeviceCtx(**{**CTX.__dict__, "admin_password": "Adm"})
    assert "static.security.user_password = admin:Adm\n" in render("yealink", "T46U", ctx)[1].decode()
    assert "<P2>Adm</P2>" in render("grandstream", "GXP2170", ctx)[1].decode()
    assert "<WEB CONFIG MODULE>\nWeb Server Password     :Adm\n" in render("fanvil", "X4U", ctx)[1].decode()


@pytest.mark.parametrize("vendor", ["yealink", "fanvil"])
def test_line_injection_is_stripped(vendor: str) -> None:
    evil = DeviceCtx(**{**CTX.__dict__, "display_name": "A\r\naccount.1.password = x",
                        "keys": (KeySpec(1, "blf", "102\nstatic.x = 1", "L\x00b"),)})
    text = render(vendor, "M", evil)[1].decode()
    assert "\naccount.1.password = x" not in text and "\nstatic.x = 1" not in text
    assert "Aaccount.1.password = x" in text and "102static.x = 1" in text and "Lb" in text


def test_grandstream_xml_escaped_and_valid() -> None:
    ctx = DeviceCtx(**{**CTX.__dict__, "display_name": "A&B <x> \"q\" 'a'\x01", "password": "p<&>"})
    root = ET.fromstring(render("grandstream", "GXP2170", ctx)[1])
    values = {el.tag: el.text for el in root.find("config")}
    assert values["P3"] == "A&B <x> \"q\" 'a'"
    assert values["P34"] == "p<&>"
    assert root.findtext("mac") == "805ec0aabbcc"


def test_extra_lines_appended() -> None:
    ctx = DeviceCtx(**{**CTX.__dict__, "extra": "features.dnd.enable = 1\r\n\n"})
    assert render("yealink", "T46U", ctx)[1].decode().endswith("linekey.1.label = Vali\nfeatures.dnd.enable = 1\n")
    gs = DeviceCtx(**{**CTX.__dict__, "extra": "P8 = 1\nP99=a&b"})
    config = ET.fromstring(render("grandstream", "GXP2170", gs)[1]).find("config")
    assert config.findtext("P8") == "1" and config.findtext("P99") == "a&b"
    fv = DeviceCtx(**{**CTX.__dict__, "extra": "<PHONE FEATURE MODULE>\nEnable DND :1"})
    assert render("fanvil", "X4U", fv)[1].decode().endswith("Fkey1 Title             :Vali\n\n<PHONE FEATURE MODULE>\n"
                                                              "Enable DND :1\n")


def test_masked_hides_all_secrets() -> None:
    ctx = masked(DeviceCtx(**{**CTX.__dict__, "admin_password": "Adm"}))
    for vendor in ("yealink", "grandstream", "fanvil"):
        text = render(vendor, "M", ctx)[1].decode()
        assert "Pw1" not in text and "Adm" not in text and "***" in text
    assert masked(CTX).admin_password is None


@pytest.mark.parametrize(("key", "yealink_type"), [
    ("blf", 16), ("speed_dial", 13), ("line", 15), ("park", 10), ("dnd", 5), ("none", 0)])
def test_yealink_key_types(key: str, yealink_type: int) -> None:
    ctx = DeviceCtx(**{**CTX.__dict__, "keys": (KeySpec(3, key, "701"),)})
    assert f"linekey.3.type = {yealink_type}\n" in render("yealink", "T46U", ctx)[1].decode()


def test_transport_and_port() -> None:
    ctx = DeviceCtx(**{**CTX.__dict__, "transport": "tls", "server_port": 5061})
    text = render("yealink", "T46U", ctx)[1].decode()
    assert "transport_type = 2\n" in text and "sip_server.1.port = 5061\n" in text
    assert "<P47>pbx.local:5061</P47>" in render("grandstream", "G", ctx)[1].decode()


@pytest.mark.parametrize(("tz", "minutes", "text", "posix"), [
    ("Asia/Tashkent", 300, "+5", "<+05>-5"),
    ("Asia/Kolkata", 330, "+5:30", "<+0530>-5:30"),
    ("America/St_Johns", -210, "-3:30", "<-0330>3:30"),
    ("UTC", 0, "+0", "<+00>0"),
])
def test_timezone_forms(tz: str, minutes: int, text: str, posix: str) -> None:
    assert r.utc_offset_minutes(tz) == minutes
    assert r._offset_text(tz) == text
    assert r._posix_tz(tz) == posix


def test_fanvil_key_without_value_has_no_suffix() -> None:
    assert r._fanvil_key_pairs(KeySpec(2, "blf", "", "")) == [("Fkey2 Type", 1), ("Fkey2 Value", ""), ("Fkey2 Title", "")]
    assert r._fanvil_key_pairs(KeySpec(2, "line", "1", ""))[1] == ("Fkey2 Value", "1")


def test_helpers() -> None:
    assert r.device_filename("grandstream", "aa") == "cfgaa.xml" and r.device_filename("fanvil", "aa") == "aa.cfg"
    assert r.content_type("grandstream") == "application/xml" and r.content_type("yealink") == "text/plain"
    assert r.line_value("  a\tb \n") == "ab"
