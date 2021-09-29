from datetime import datetime
import json
import random
import frappe
from frappe import auth
import base64
import os
from frappe.utils import get_site_name
from frappe.utils.data import escape_html
from frappe.website.utils import is_signup_enabled
from redis import DataError
import requests


@frappe.whitelist(allow_guest=True)
def login(usr, pwd):
    try:
        login_manager = frappe.auth.LoginManager()
        login_manager.authenticate(user=usr, pwd=pwd)
        login_manager.post_login()
    except frappe.exceptions.AuthenticationError:
        frappe.clear_messages()
        frappe.local.response["message"] = {
            "success_key": 0,
            "message": "Authentication Error!"
        }

        return

    api_generate = generate_keys(frappe.session.user)
    user = frappe.get_doc('User', frappe.session.user)

    frappe.response["message"] = {
        "success_key": 1,
        "message": "Authentication success",
        "sid": frappe.session.sid,
        "api_key": user.api_key,
        "api_secret": api_generate,
        "username": user.username,
        "email": user.email,
        "role": user.roles[0].role
    }

def generate_keys(user):
    user_details = frappe.get_doc('User', user)
    api_secret = frappe.generate_hash(length=15)

    if not user_details.api_key:
        api_key = frappe.generate_hash(length=15)
        # user_details.api_key = api_key
        frappe.db.set_value('User', user, 'api_key', api_key)

    # user_details.api_secret = api_secret
    # user_details.flags.ignore_permissions = True
    # user_details.save()
    frappe.db.set_value('User', user, 'api_secret', api_secret)
    frappe.db.commit()

    return api_secret

@frappe.whitelist(allow_guest=True)
def get_doctype_images(doctype, docname):

    attachments = frappe.get_all("File", fields=["attached_to_name", "file_name", "file_url", "is_private"], filters={
                                 "attached_to_name": docname, "attached_to_doctype": doctype})
    site_path = frappe.get_site_path('private')
    site_name = get_site_name(frappe.local.request.host)
    x = frappe.utils.get_files_path('GP-Gate C-00282.jpg', is_private=1)

    resp = []
    for attachment in attachments:
        # file_path = site_path + attachment["file_url"]
        x = frappe.utils.get_files_path(attachment['file_name'], is_private=1)
        with open(x, "rb") as f:
            # encoded_string = base64.b64encode(image_file.read())
            img_content = f.read()
            img_base64 = base64.b64encode(img_content).decode()
            img_base64 = 'data:image/jpeg;base64,' + img_base64

        resp.append({"image": img_base64})

    return resp

@frappe.whitelist(allow_guest=True)
def gm_write_file(data, filename, docname):
    try:

        system_settings = frappe.get_doc('System Settings')
        
        # filename_ext = f'/home/expressdev/frappe-bench/sites/develop.etplraipur.in/private/files/{filename}'
        # filename_ext = f'/home/express/frappe-bench/sites/erp.etplraipur.in/private/files/{filename}'
        
        filename_ext = f'{system_settings.image_upload_path}/{filename}'
        base64data = data.replace('data:image/jpeg;base64,', '')
        base64data = data.replace('data:image/*;base64,', '')
        imgdata = base64.b64decode(base64data)
        with open(filename_ext, 'wb') as file:
            file.write(imgdata)

        doc = frappe.get_doc(
            {
                "file_name": filename,
                "is_private": 1,
                "file_url": f'/private/files/{filename}',
                "attached_to_doctype": "Gate Entry",
                "attached_to_name": docname,
                "doctype": "File",
            }
        )
        doc.flags.ignore_permissions = True
        doc.insert()

    except Exception as e:
        return e

def create_transport_jv(doc, method):
    if doc.purch_bilty_amt_jv > 0:

        jv = frappe.get_doc({
            "title": doc.purch_transporter_name,
            "voucher_type": "Journal Entry",
            # "naming_series": "ACC-JV-.YYYY.-",
            "posting_date": doc.posting_date,
            "bill_no": doc.name,
            "bill_date": doc.posting_date,
            "pay_to_recd_from": doc.purch_transporter_name,
            "doctype": "Journal Entry",
            "user_remark": doc.remarks,
            "accounts": [
                {
                    "parentfield": "accounts",
                    "parenttype": "Journal Entry",
                    "account": "Transportation Expenses - ETPL",
                    "account_type": "Expense Account",
                    "cost_center": "Main - ETPL",
                    "account_currency": "INR",
                    "debit_in_account_currency": doc.purch_bilty_amt_jv,
                    "debit": doc.purch_bilty_amt_jv,
                    "credit_in_account_currency": 0,
                    "credit": 0,
                    "is_advance": "No",
                    "against_account": doc.purch_transporter_name,
                    "doctype": "Journal Entry Account"
                },
                {
                    "parentfield": "accounts",
                    "parenttype": "Journal Entry",
                    "account": f'{doc.purch_transporter_name} - ETPL',
                    "account_type": "Payable",
                    "party_type": "Supplier",
                    "party": doc.purch_transporter_name,
                    "cost_center": "Main - ETPL",
                    "account_currency": "INR",
                    "exchange_rate": 1,
                    "debit_in_account_currency": 0,
                    "debit": 0,
                    "credit_in_account_currency": doc.purch_bilty_amt_jv,
                    "credit": doc.purch_bilty_amt_jv,
                    "is_advance": "No",
                    "against_account": "Transportation Expenses - ETPL",
                    "doctype": "Journal Entry Account"
                }
            ]
        })

        jv.insert()

        frappe.msgprint(f'JV Created {jv.name}')

@frappe.whitelist(allow_guest=True)
def generate_otp(mobile):

    if len(mobile) != 10:
        frappe.local.response["message"] = {
            "success_key": 0,
            "message": "Invalid Mobile Number"
        }
        return 

    if not mobile:
        frappe.local.response["message"] = {
            "success_key": 0,
            "message": "Please provide mobile number"
        }
        return 


    # otp = str(random.randint(1000,9999))
    
    # user = frappe.db.get_list('User', filters={'mobile_no': mobile}, fields=['email', 'first_name', 'last_name'])
    user_email = frappe.db.get_all('User', filters={'mobile_no': mobile}, fields=['email'])
    # print(user_email)
    if not user_email:
        frappe.local.response["message"] = {
            "success_key": 0,
            "message": "Account does not exits"
        }
        return 

    user = frappe.get_doc('User', user_email[0]['email'])
    otp = "1234"
    # try:
    #     # url = f"http://login.bulksms.org/app/smsapi/index.php?key=45B925523F11E0&campaign=4465&routeid=101085&type=text&contacts={_mobile}&senderid=SABUAC&msg=your%20OTP%20for%20login%20to%20acc.sabooco.com%20is%20{otp}&template_id=1407162626157392009"
    #     otp = str(random.randint(1000,9999))
    #     url = f"http://bhashsms.com/api/sendmsg.php?user=Steptech&pass=123456&sender=STEPTC&phone={mobile}&text=Dear%20Customer,%20Your%20OTP%20is%20{otp}.%20Regards%20Chunnilal%20Kesrimal%20Barolta&priority=ndnd&stype=normal"
    #     r = requests.get(url)
    #     if r.status_code != 200:
    #         frappe.local.response["message"] = {
    #             "success_key": 0,
    #             "message": "Account does not exits"
    #         }
    #         return 
    # except Exception as e:
    #     frappe.local.response["message"] = {
    #         "success_key": 0,
    #         "message": str(e)
    #     }
    #     return 

    try:
        name = frappe.generate_hash()[0:9]
        frappe.db.sql(""" INSERT INTO `tabOTP Auth Log` (name, mobile_no, user, otp, time) VALUES (%s, %s, %s, %s, NOW())""", (name, mobile, user.name, otp))
        frappe.db.commit()

    except Exception as e:
        return e

    frappe.local.response["message"] = {
        "success_key": 1,
        "message": "OTP Sent"
    }
    return 
    
@frappe.whitelist(allow_guest=True)
def validate_otp(mobile, otp):

    if not mobile or not otp:
        frappe.local.response["message"] = {
            "success_key": 0,
            "message": "invalid inputs"
        }
        return
    
    x = frappe.db.count('OTP Auth Log',
        {
            'mobile_no': mobile,
            'otp': otp
        })

    if not x > 0:
        frappe.local.response["message"] = {
            "success_key": 0,
            "message": "invalid otp, please try again with correct otp"
        }
        return

    user_email = frappe.db.get_all('User', filters={'mobile_no': mobile}, fields=['email'])
    # print(user_email)
    if not user_email:
        frappe.local.response["message"] = {
            "success_key": 0,
            "message": "Account does not exits"
        }
        return 

    user = frappe.get_doc('User', user_email[0]['email'])
    
    api_generate = generate_keys(user.name)
    user_resp = frappe.get_doc('User', user.name)

    frappe.response["message"] = {
        "success_key": 1,
        "message": "Authentication success",
        "api_key": user_resp.api_key,
        "api_secret": api_generate,
        "username": user.username,
        "email": user_resp.email,
        "role": user_resp.roles[0].role
        }

@frappe.whitelist(allow_guest=True)
def sign_up(email, full_name, mobile):
    if not is_signup_enabled():
        frappe.response["message"] = {
            "success_key": 0,
            "message": "Signup is",
        }

    user = frappe.db.get("User", {"email": email})
    if user:
        if user.disabled:
            frappe.response["message"] = {
                "success_key": 0,
                "message": "User is disabled",
            }
            return
        else:
            frappe.response["message"] = {
                "success_key": 0,
                "message": "User Already Registered",
            }
            return
    else:
        if frappe.db.sql("""select count(*) from tabUser where
            HOUR(TIMEDIFF(CURRENT_TIMESTAMP, TIMESTAMP(modified)))=1""")[0][0] > 300:

            frappe.response["message"] = {
                "success_key": 0,
                "message": "Too many Registrations",
            }

        from frappe.utils import random_string
        user = frappe.get_doc({
            "doctype":"User",
            "email": email,
            "mobile_no": mobile,
            "send_welcome_email": 0,
            "first_name": escape_html(full_name),
            "enabled": 1,
            "new_password": random_string(10),
            "user_type": "Website User"
        })
        user.flags.ignore_permissions = True
        user.flags.ignore_password_policy = True
        user.insert()
        frappe.db.commit()

        frappe.response["message"] = {
            "success_key": 1,
            "message": "Signup Success, Team will get in touch with you soon",
        }


def get_user_info(api_key, api_sec):
    # api_key  = frappe.request.headers.get("Authorization")[6:21]
    # api_sec  = frappe.request.headers.get("Authorization")[22:]
    doc = frappe.db.get_value(
        doctype='User',
        filters={"api_key": api_key, "api_secret": api_sec},
        fieldname=["name"]
    )
    if doc:
        return doc
    
    return None


@frappe.whitelist(allow_guest=True)
def get_orders():
    api_key  = frappe.request.headers.get("Authorization")[6:21]
    api_sec  = frappe.request.headers.get("Authorization")[22:]

    user_email = get_user_info(api_key, api_sec)
    if not user_email:
        frappe.response["message"] = {
            "success_key": 0,
            "message": "Unauthorised Access",
        }
        return 

    orders = frappe.db.get_all('Sales Order',
        filters={
            'contact_email': user_email,
            'docstatus': 1
        },
        fields=['name', 'transaction_date', 'docstatus', 'rounded_total', 'billing_status', 'customer', 'delivery_status', 'delivery_date', 'status']
    )
    return orders


@frappe.whitelist(allow_guest=True)
def get_order_details(name):
    api_key  = frappe.request.headers.get("Authorization")[6:21]
    api_sec  = frappe.request.headers.get("Authorization")[22:]

    user_email = get_user_info(api_key, api_sec)
    if not user_email:
        frappe.response["message"] = {
            "success_key": 0,
            "message": "Unauthorised Access",
        }
        return 

    order = frappe.get_doc('Sales Order', name)
    return order


@frappe.whitelist(allow_guest=True)
def ledger(from_date, to_date):
    api_key  = frappe.request.headers.get("Authorization")[6:21]
    api_sec  = frappe.request.headers.get("Authorization")[22:]

    user_email = get_user_info(api_key, api_sec)
    if not user_email:
        frappe.response["message"] = {
            "success_key": 0,
            "message": "Unauthorised Access",
        }
        return

    customer = frappe.db.get_all('Customer',
        filters={
            'email_id': user_email,
            'disabled': 0
        },
        fields=['customer_name']
    )

    if not len(customer) > 0:
        frappe.response["message"] = {
            "success_key": 0,
            "message": "Contact Administrator",
        }
        return

    gl_op = frappe.db.sql("""
        SELECT
            'Opening Balance' as voucher_type, sum(debit) debit, sum(credit) credit
        FROM `tabGL Entry`
        WHERE party = %s AND docstatus = 1 AND is_cancelled = 0
        AND
        posting_date < %s
    """, (customer[0].customer_name, from_date), as_dict=1)

    gl = frappe.db.sql("""
        SELECT 
            posting_date, party, `against`, sum(debit) as debit, sum(credit) as credit, voucher_type, voucher_no, remarks
        FROM `tabGL Entry`
        WHERE party = %s AND docstatus = 1 AND is_cancelled = 0
        AND
        posting_date BETWEEN %s AND %s GROUP BY voucher_no ORDER BY posting_date ASC
    """, (customer[0].customer_name, from_date, to_date), as_dict=1)

    return gl_op + gl



@frappe.whitelist(allow_guest=True)
def outstanding(from_date, to_date):
    api_key  = frappe.request.headers.get("Authorization")[6:21]
    api_sec  = frappe.request.headers.get("Authorization")[22:]

    user_email = get_user_info(api_key, api_sec)
    if not user_email:
        frappe.response["message"] = {
            "success_key": 0,
            "message": "Unauthorised Access",
        }
        return

    customer = frappe.db.get_all('Customer',
        filters={
            'email_id': user_email,
            'disabled': 0
        },
        fields=['customer_name']
    )

    if not len(customer) > 0:
        frappe.response["message"] = {
            "success_key": 0,
            "message": "Contact Administrator",
        }
        return

    gl = frappe.db.sql("""
        SELECT
            posting_date, `name`, party, voucher_no, SUM(debit) debit, SUM(credit) credit,
            CASE WHEN is_opening = %s then voucher_no ELSE against_voucher END AS against_voucher_1
        FROM `tabGL Entry`
        WHERE `party` = %s AND is_cancelled = 0
        GROUP BY against_voucher_1
        ORDER BY posting_date DESC
        """, ('Yes', customer[0].customer_name), as_dict=1)

    return gl


@frappe.whitelist(allow_guest=True)
def create_gate_entry():
    payload = json.loads(frappe.request.data)
    payload['doctype'] = 'Gate Entry'
    # return payload
    gate_entry = frappe.get_doc(payload)
    gate_entry.flags.ignore_permissions = True
    gate_entry.save()

    frappe.response["message"] = {
            "success_key": 1,
            "message": "Entry Created Successfully",
            "name": gate_entry.name
    }
    return

@frappe.whitelist(allow_guest=True)
def update_gate_entry():
    payload = json.loads(frappe.request.data)
    payload['doctype'] = 'Gate Entry'
    # return payload
    vehicle_number = payload['vehicle_number']
    godown = payload['godown'] 
    invoice_date = payload['invoice_date']
    invoice_no = payload['reference_number']
    invoice_value = payload['invoice_value']
    item_group = payload['item_group']
    lr_amount = payload['lr_amount']
    lr_date = payload['lr_date']
    lr_number = payload['lr_number']
    packages = payload['packages']
    party_name = payload['party_name']
    transporter_name = payload['transporter_name']
    weight = payload['weight']
    name = payload['name']
    notes = payload['notes']
    driver_name = payload['driver_name']
    driver_contact = payload['driver_contact']

    frappe.db.sql("""
        UPDATE `tabGate Entry` SET vehicle_number=%s, godown=%s, invoice_date=%s, invoice_no=%s,
                invoice_value=%s, item_group=%s, lr_amount=%s, lr_date=%s, lr_number=%s, packages=%s,
                party_name=%s, reference_number=%s, transporter_name=%s, weight=%s, notes=%s, driver_name=%s, driver_contact=%s
                WHERE name = %s
    """, (vehicle_number, godown, invoice_date, invoice_no, invoice_value, item_group, lr_amount, lr_date, lr_number, packages, party_name, invoice_no, transporter_name, weight, notes, driver_name, driver_contact, name))
    frappe.db.commit()

    frappe.response["message"] = {
            "success_key": 1,
            "message": "Entry Updated Successfully"
    }
    return

@frappe.whitelist(allow_guest=True)
def gate_entry_list():
    api_key  = frappe.request.headers.get("Authorization")[6:21]
    api_sec  = frappe.request.headers.get("Authorization")[22:]

    user_email = get_user_info(api_key, api_sec)
    if not user_email:
        frappe.response["message"] = {
            "success_key": 0,
            "message": "Unauthorised Access",
        }
        return

    ge = frappe.db.sql("""
        SELECT
            *
        FROM `tabGate Entry`
        WHERE ge_status = 'In'
        ORDER BY in_time DESC
        """, as_dict=1)

    return ge

@frappe.whitelist(allow_guest=True)
def gate_entry_one():
    api_key  = frappe.request.headers.get("Authorization")[6:21]
    api_sec  = frappe.request.headers.get("Authorization")[22:]
    docname  = frappe.request.headers.get("docname")

    user_email = get_user_info(api_key, api_sec)
    if not user_email:
        frappe.response["message"] = {
            "success_key": 0,
            "message": "Unauthorised Access",
        }
        return

    ge = frappe.db.sql("""
        SELECT
            *
        FROM `tabGate Entry`
        WHERE ge_status = 'In' and %s
        ORDER BY in_time DESC
        """, docname, as_dict=1)

    return ge

