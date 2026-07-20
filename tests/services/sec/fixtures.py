"""Realistic (trimmed) HTML fixtures mirroring live market.sec.or.th result markup.

Structures captured live 2026-07-20: a FS search returns several ``card-heading`` + ``table``
sections at once; MD&A uses Date/Time/Heading/Link columns (no Name); 56-1/56-2 use
Name/Year/Receive Date; some rows link via /public/idisc/Download?FILEID=…, others via
/ipos/Common/IPOSGetFile.aspx?id=…
"""

DL = "https://market.sec.or.th/public/idisc/Download?FILEID="
IPOS = "https://market.sec.or.th/ipos/Common/IPOSGetFile.aspx?id="

# A FS search response panel: revised (empty) + Financial Statements (2) + KFR (1) + MD&A (1).
FS_SEARCH_HTML = f"""
<div id="ctl00_CPH_pnlControl">
  <div class="card card-table"><div class="card-heading">The Financial Statements which need to be revised ( 0 record(s) found)</div>
    <table id="gPP06T01"><tbody>
      <tr><th>Order Date</th><th>Company Name</th><th>Reviewed Financial Statement</th><th>Details</th></tr>
      <tr><td colspan="4">Data not found</td></tr>
    </tbody></table>
  </div>
  <div class="card card-table"><div class="card-heading">Finanacial Statements ( 2 record(s) found)</div>
    <table id="gPP06T02"><tbody>
      <tr><th>Name</th><th>Year</th><th>Status</th><th>Type</th><th>Period</th><th>As Of</th><th>Details</th></tr>
      <tr><td>CP ALL PUBLIC COMPANY LIMITED</td><td>2026</td><td>Reviewed</td><td>Company</td><td>Q1</td><td>31/03/2026</td>
          <td class="icon30"><a href="{DL}dat/news/202605/0737FIN.zip" target="_blank"><img></a></td></tr>
      <tr><td>CP ALL PUBLIC COMPANY LIMITED</td><td>2025</td><td>Reviewed</td><td>Consolidated</td><td>Q3</td><td>30/09/2025</td>
          <td class="icon30"><a href="{IPOS}726416&amp;sq=0&amp;v=10" target="_blank"><img></a></td></tr>
    </tbody></table>
  </div>
  <div class="card card-table"><div class="card-heading">Key Financial Ratio ( 1 record(s) found)</div>
    <table id="gPP06T03"><tbody>
      <tr><th>Name</th><th>Business Type</th><th>Type</th><th>Period</th><th>Year</th><th>As Of</th><th>Details</th></tr>
      <tr><td>CP ALL PUBLIC COMPANY LIMITED</td><td>Trading</td><td>Consolidated</td><td>Year</td><td>2025</td><td>31/12/2025</td>
          <td><a href="{IPOS}693598&amp;sq=0&amp;v=10"><img></a></td></tr>
    </tbody></table>
  </div>
  <div class="card card-table"><div class="card-heading">Management's Discussion and Analysis ( 1 record(s) found)</div>
    <table id="gPP06T04"><tbody>
      <tr><th>Date</th><th>Time</th><th>Heading</th><th>Link</th></tr>
      <tr><td>25/02/2026</td><td>17:36</td><td>Management Discussion and Analysis Yearly Ending 31-Dec-2025</td>
          <td><a href="{DL}dat/news/202602/0737NWS.pdf"><img></a></td></tr>
    </tbody></table>
  </div>
</div>
"""

# A FS search where the Financial Statements section is truncated (1 inline row) with a
# "display all results" ViewMore link (fs-norm).
FS_TRUNCATED_HTML = f"""
<div id="ctl00_CPH_pnlControl">
  <div class="card card-table"><div class="card-heading">Finanacial Statements ( 3 record(s) found)</div>
    <table id="gPP06T02"><tbody>
      <tr><th>Name</th><th>Year</th><th>Status</th><th>Type</th><th>Period</th><th>As Of</th><th>Details</th></tr>
      <tr><td>CP ALL PUBLIC COMPANY LIMITED</td><td>2026</td><td>Reviewed</td><td>Company</td><td>Q1</td><td>31/03/2026</td>
          <td><a href="{DL}dat/news/inline_only.zip"><img></a></td></tr>
      <tr><td colspan="7"><a href="/public/idisc/en/ViewMore/fs-norm?uniqueIDReference=0000003875&amp;dateFrom=20200101&amp;dateTo=20260720">Click here to display all results</a></td></tr>
    </tbody></table>
  </div>
</div>
"""

# The ViewMore fs-norm page: the COMPLETE FS list (3 rows).
FS_VIEWMORE_HTML = f"""
<div class="card card-table"><div class="card-heading">Finanacial Statements ( 3 record(s) found)</div>
  <table id="gv"><tbody>
    <tr><th>Name</th><th>Year</th><th>Status</th><th>Type</th><th>Period</th><th>As Of</th><th>Details</th></tr>
    <tr><td>CP ALL PUBLIC COMPANY LIMITED</td><td>2026</td><td>Reviewed</td><td>Company</td><td>Q1</td><td>31/03/2026</td>
        <td><a href="{DL}dat/news/full_1.zip"><img></a></td></tr>
    <tr><td>CP ALL PUBLIC COMPANY LIMITED</td><td>2025</td><td>Audited</td><td>Company</td><td>Year</td><td>31/12/2025</td>
        <td><a href="{DL}dat/news/full_2.zip"><img></a></td></tr>
    <tr><td>CP ALL PUBLIC COMPANY LIMITED</td><td>2025</td><td>Audited</td><td>Consolidated</td><td>Year</td><td>31/12/2025</td>
        <td><a href="{DL}dat/news/full_3.zip"><img></a></td></tr>
  </tbody></table>
</div>
"""

FORM_56_1_HTML = f"""
<div id="ctl00_CPH_pnlControl">
  <div class="card card-table"><div class="card-heading">Form 56-1 : Annual Registration Statements ( 2 record(s) found)</div>
    <table id="g561"><tbody>
      <tr><th>Name</th><th>Year</th><th>Receive Date</th><th>Details</th></tr>
      <tr><td>CP ALL PUBLIC COMPANY LIMITED</td><td>2025</td><td>26/03/2026</td>
          <td><a href="{DL}dat/f56/0737E1N.zip"><img></a></td></tr>
      <tr><td>CP ALL PUBLIC COMPANY LIMITED</td><td>2024</td><td>31/03/2025</td>
          <td><a href="{DL}dat/f56/0737ONE.zip"><img></a></td></tr>
    </tbody></table>
  </div>
</div>
"""

FORM_56_2_HTML = f"""
<div id="ctl00_CPH_pnlControl">
  <div class="card card-table"><div class="card-heading">Form 56-2 : Annual Reports ( 1 record(s) found)</div>
    <table id="g562"><tbody>
      <tr><th>Name</th><th>Year</th><th>Receive Date</th><th>Details</th></tr>
      <tr><td>CP ALL PUBLIC COMPANY LIMITED</td><td>2025</td><td>26/03/2026</td>
          <td><a href="{DL}dat/annual/0737E1N.zip"><img></a></td></tr>
    </tbody></table>
  </div>
</div>
"""

# The GET page carrying the hidden ASP.NET tokens.
REPORT_PAGE_HTML = """
<form id="aspnetForm">
  <input type="hidden" name="__VIEWSTATE" id="__VIEWSTATE" value="STATE123==" />
  <input type="hidden" name="__VIEWSTATEGENERATOR" id="__VIEWSTATEGENERATOR" value="688223AE" />
  <input type="hidden" name="__EVENTVALIDATION" id="__EVENTVALIDATION" value="EVAL456==" />
</form>
"""

# The Thai soft-404 body served under HTTP 200 for a dead FILEID.
FILE_NOT_FOUND_HTML = "ไม่พบไฟล์ที่ระบุ<br/><a href='javascript:history.back();'>ย้อนกลับ</a>"

COMPANY_SEARCH_JSON = [
    {"Text": "CP ALL PUBLIC COMPANY LIMITED", "Value": "0000003875", "Flag": True},
]
COMPANY_SEARCH_MULTI_JSON = [
    {
        "Text": "PTT AROMATICS AND REFINING PUBLIC COMPANY LIMITED",
        "Value": "0000006634",
        "Flag": False,
    },
    {"Text": "PTT PUBLIC COMPANY LIMITED", "Value": "0000001111", "Flag": True},
]
