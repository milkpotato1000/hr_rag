"""Optional, identity-bearing remote provenance; local snapshots stay unchanged."""
from datetime import datetime
import re
from ..storage import require


def validate_origin(origin,original_sha256):
    required={'provider','file_id','remote_version','modified_time','mime_type','export_mime','downloaded_sha256','consistency','execution_kind'}
    require(isinstance(origin,dict) and set(origin)==required,'invalid_origin','snapshot')
    require(origin['provider']=='google_drive' and origin['consistency']=='metadata_before_after' and origin['execution_kind'] in ('live','test_fixture'),'invalid_origin','snapshot')
    require(isinstance(origin['file_id'],str) and re.fullmatch('[A-Za-z0-9_-]{1,200}',origin['file_id']),'invalid_origin','snapshot')
    require(isinstance(origin['remote_version'],str) and re.fullmatch('[0-9]+',origin['remote_version']),'invalid_origin','snapshot')
    require(isinstance(origin['modified_time'],str),'invalid_origin','snapshot')
    try:valid=datetime.fromisoformat(origin['modified_time'].replace('Z','+00:00')).tzinfo is not None
    except ValueError:valid=False
    require(valid and origin['mime_type'] in ('application/pdf','text/plain','text/markdown','application/vnd.google-apps.document'),'invalid_origin','snapshot')
    require(origin['export_mime']==('application/pdf' if origin['mime_type']=='application/vnd.google-apps.document' else None),'invalid_origin','snapshot')
    require(origin['downloaded_sha256']==original_sha256,'origin_hash_mismatch','snapshot')
    return origin
