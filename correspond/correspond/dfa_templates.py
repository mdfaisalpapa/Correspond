import frappe

TEMPLATES = {
    "Office Memorandum": """
<div style="font-family: 'Times New Roman', Times, serif; padding: 25px; line-height: 1.6; color: #111;">
    <div style="text-align: center; margin-bottom: 25px;">
        <h4 style="margin: 0; text-transform: uppercase; font-weight: bold; letter-spacing: 1px;">GOVERNMENT OF INDIA</h4>
        <h5 style="margin: 3px 0; font-weight: bold;">MINISTRY / DEPARTMENT OF _________________</h5>
        <div style="font-size: 13px; margin-top: 5px;">New Delhi, Dated: {{ receipt_date or '_________________' }}</div>
    </div>

    <div style="text-align: center; margin: 25px 0;">
        <h4 style="text-decoration: underline; font-weight: bold; margin: 0;">OFFICE MEMORANDUM</h4>
    </div>

    <div style="margin-bottom: 20px;">
        <b>Subject:</b> <span style="font-weight: bold; text-decoration: underline;">{{ subject or '[Insert Subject]' }}</span>
    </div>

    <div style="margin-bottom: 20px; text-align: justify;">
        <p>The undersigned is directed to refer to this Department's O.M. of even number dated ____________ on the subject cited above and to convey the following decision/clarification:</p>
        <p>2. &nbsp; [Insert operative body paragraphs here]</p>
        <p>3. &nbsp; This issues with the approval of the Competent Authority.</p>
    </div>

    <div style="display: flex; justify-content: flex-end; margin-top: 40px;">
        <div style="text-align: center; min-width: 200px;">
            <br><br>
            <div style="font-weight: bold;">({{ sender_name or 'Under Secretary to the Govt. of India' }})</div>
            <div style="font-size: 13px;">Tel: __________________</div>
        </div>
    </div>

    <div style="margin-top: 40px; border-top: 1px dashed #ccc; padding-top: 15px;">
        <b>To:</b>
        <div style="margin-left: 20px;">
            1. All Ministries / Departments of the Government of India.<br>
            2. Notice Board / Website.
        </div>
    </div>
</div>
""",

    "Demi-Official (D.O.) Letter": """
<div style="font-family: 'Times New Roman', Times, serif; padding: 25px; line-height: 1.6; color: #111;">
    <div style="display: flex; justify-content: space-between; border-bottom: 2px solid #800000; padding-bottom: 15px; margin-bottom: 20px;">
        <div>
            <h5 style="margin: 0; font-weight: bold; color: #800000;">{{ sender_name or 'OFFICER NAME' }}</h5>
            <div style="font-size: 13px;">{{ sender_designation or 'Joint Secretary' }}</div>
            <div style="font-size: 12px;">Tel: __________________</div>
        </div>
        <div style="text-align: right;">
            <h5 style="margin: 0; font-weight: bold; text-transform: uppercase;">GOVERNMENT OF INDIA</h5>
            <div style="font-size: 13px;">DEPARTMENT OF _________________</div>
            <div style="font-size: 12px;">Dated: {{ receipt_date or '_________________' }}</div>
        </div>
    </div>

    <div style="margin: 20px 0;">
        <b>D.O. No.:</b> {{ dfa_number or '___________________' }}
    </div>

    <div style="margin-bottom: 15px;">
        Dear {{ recipient_name or 'Shri/Smt. ___________' }},
    </div>

    <div style="margin-bottom: 20px; text-align: justify;">
        <p>Kindly refer to your communication regarding <b>{{ subject or '[Insert Subject]' }}</b>.</p>
        <p>[Insert key discussion points / guidance here]</p>
        <p>I would appreciate your personal intervention to ensure expeditious completion of this matter.</p>
    </div>

    <div style="margin: 25px 0;">
        With regards,
    </div>

    <div style="display: flex; justify-content: flex-end; margin-top: 30px;">
        <div style="text-align: center; min-width: 200px;">
            <div>Yours sincerely,</div>
            <br><br>
            <div style="font-weight: bold;">({{ sender_name or 'Officer Name' }})</div>
        </div>
    </div>

    <div style="margin-top: 35px; border-top: 1px solid #ccc; padding-top: 10px;">
        <b>To:</b><br>
        {{ recipient_name or 'Shri/Smt. ________________' }}<br>
        {{ recipient_designation or 'Designation' }}<br>
        {{ recipient_organization or 'Ministry/Department' }}
    </div>
</div>
""",

    "Sanction Order": """
<div style="font-family: 'Times New Roman', Times, serif; padding: 25px; line-height: 1.6; color: #111;">
    <div style="text-align: center; margin-bottom: 25px;">
        <h4 style="margin: 0; font-weight: bold; text-transform: uppercase;">GOVERNMENT OF INDIA</h4>
        <h5 style="margin: 3px 0; font-weight: bold;">MINISTRY / DEPARTMENT OF _________________</h5>
        <div style="font-size: 13px;">Date: {{ receipt_date or '_________________' }}</div>
    </div>

    <div style="text-align: center; margin: 20px 0;">
        <h4 style="text-decoration: underline; font-weight: bold; margin: 0;">ADMINISTRATIVE & FINANCIAL SANCTION ORDER</h4>
    </div>

    <div style="margin-bottom: 20px; text-align: justify;">
        <p>Sanction of the Competent Authority is hereby accorded in terms of Rule _________________ of General Financial Rules (GFR), 2017 for the procurement/expenditure on:</p>
        <div style="margin: 15px 0; padding: 10px; background: #fdfdfd; border-left: 3px solid #333;">
            <b>Scheme / Head:</b> ___________________________<br>
            <b>Sanctioned Amount:</b> ₹ ____________________ (Rupees ____________________________________ only)
        </div>
        <p>2. &nbsp; The expenditure involved is debitable to Major Head '______', Minor Head '______', Object Head '______' under Demand No. '______' for the financial year {{ current_year or '2026-27' }}.</p>
        <p>3. &nbsp; This issues with the concurrence of the Integrated Finance Division (IFD) vide their Dy. No. ________ dated ____________.</p>
    </div>

    <div style="display: flex; justify-content: flex-end; margin-top: 40px;">
        <div style="text-align: center; min-width: 220px;">
            <br><br>
            <div style="font-weight: bold;">({{ sender_name or 'Drawing & Disbursing Officer' }})</div>
            <div style="font-size: 13px;">Under Secretary to the Govt. of India</div>
        </div>
    </div>

    <div style="margin-top: 35px; border-top: 1px dashed #ccc; padding-top: 15px;">
        <b>Copy to:</b><br>
        1. Pay & Accounts Officer (PAO).<br>
        2. Principal Director of Audit.<br>
        3. Finance Division (IFD).
    </div>
</div>
""",

    "Circular": """
<div style="font-family: 'Times New Roman', Times, serif; padding: 25px; line-height: 1.6; color: #111;">
    <div style="text-align: center; margin-bottom: 25px;">
        <h4 style="margin: 0; font-weight: bold; text-transform: uppercase;">GOVERNMENT OF INDIA</h4>
        <h5 style="margin: 3px 0; font-weight: bold;">DEPARTMENT OF _________________</h5>
        <div style="font-size: 13px;">Dated: {{ receipt_date or '_________________' }}</div>
    </div>

    <div style="text-align: center; margin: 25px 0;">
        <h4 style="text-decoration: underline; font-weight: bold; margin: 0;">C I R C U L A R</h4>
    </div>

    <div style="margin-bottom: 20px;">
        <b>Subject:</b> <span style="font-weight: bold; text-decoration: underline;">{{ subject or '[Insert Subject]' }}</span>
    </div>

    <div style="margin-bottom: 20px; text-align: justify;">
        <p>It has been observed that __________________________________________________________________.</p>
        <p>2. &nbsp; In view of the above, all officers and staff are hereby directed to strictly adhere to the following guidelines with immediate effect:</p>
        <div style="margin-left: 20px;">
            (i) ________________________________________________<br>
            (ii) _______________________________________________
        </div>
    </div>

    <div style="display: flex; justify-content: flex-end; margin-top: 40px;">
        <div style="text-align: center; min-width: 200px;">
            <br><br>
            <div style="font-weight: bold;">({{ sender_name or 'Deputy Secretary / Director' }})</div>
        </div>
    </div>

    <div style="margin-top: 30px; border-top: 1px solid #ddd; padding-top: 10px;">
        <b>Distribution:</b><br>
        All Officers and Sections of the Department.
    </div>
</div>
"""
}

@frappe.whitelist()
def get_dfa_template(template_name):
    """Returns the default HTML boilerplate for a given Government DFA format."""
    return TEMPLATES.get(template_name, "")
