import frappe
from frappe import auth
import base64
import os
from frappe.utils import get_site_name


@frappe.whitelist(allow_guest=True)
def login(usr, pwd):
    print('user: ', usr)
    print('password', pwd)
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
        user_details.api_key = api_key

    user_details.api_secret = api_secret
    user_details.save()

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


@frappe.whitelist()
def gm_write_file(data, filename, docname):
    try:
        filename_ext = f'/home/expressdev/frappe-bench/sites/develop.etplraipur.in/private/files/{filename}'
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
        doc.insert()

    except Exception as e:
        return e