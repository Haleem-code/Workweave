import io
import httpx
# pyrefly: ignore [missing-import]
import pytest
from workweave_api.drive import selected_file
from workweave_api.ingestion import parse_file
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_google_docs_and_native_sheets_adapters():
    def handler(request):
        if request.url.host=='sheets.googleapis.com':
            return httpx.Response(200,json={'sheets':[{'properties':{'title':'Products'},'data':[{'rowData':[{'values':[{'formattedValue':'id'},{'formattedValue':'stock'}]},{'values':[{'formattedValue':'SKU1'},{'formattedValue':'12'}]}]}]}]})
        if request.url.path.endswith('/export'):
            return httpx.Response(200,text='Fictional company guide')
        ident=request.url.path.rsplit('/',1)[-1]
        return httpx.Response(200,json={'id':ident,'name':'Guide' if ident=='doc12345' else 'Catalog','mimeType':'application/vnd.google-apps.document' if ident=='doc12345' else 'application/vnd.google-apps.spreadsheet'})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        name,content,_=await selected_file(http,{},'doc12345')
        assert name=='Guide.txt' and parse_file(name,content)['sections'][0]['text']=='Fictional company guide'
        name,content,_=await selected_file(http,{},'sheet12345')
        parsed=parse_file(name,content)
        assert parsed['tables'][0]['name']=='Products' and parsed['tables'][0]['rows']==[['SKU1','12']]
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(403))) as http:
        with pytest.raises(HTTPException) as error: await selected_file(http,{},'revoked12345')
        assert error.value.status_code==410


@pytest.mark.asyncio
async def test_corrupt_upload_has_an_actionable_error():
    from workweave_api.ingestion import preview
    with pytest.raises(ValueError, match='valid, unencrypted'):
        await preview(None, 'invalid.xlsx', b'not a workbook')
