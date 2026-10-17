from .ingestion import preview, confirm


PROFILE = {
    "id": "profile", "description": "Harbor Supply distributes packaging and maintenance supplies to local businesses. Customer commitments depend on purchase orders and unallocated warehouse stock.",
    "responsibilities": "Customer Success owns customer commitments. Purchasing owns supplier follow-up.",
    "procedure": "When a delivery becomes late, investigate affected commitments, check unallocated stock, and create an internal review task for the current order owner. Propose customer communications for human review.",
    "confirmed": True,
}
TABLES = {
    "Teams.csv": "id,name\nCS,Customer Success\nBUY,Purchasing\n",
    "Suppliers.csv": "id,name,owner\nSUP1,Northstar Packaging,BUY\nSUP2,Eastbank Tools,BUY\n",
    "Products.csv": "id,name,stock,supplier_id\nBOX,Shipping cartons,2,SUP1\nTAPE,Packing tape,30,SUP1\nTOOL,Maintenance kit,0,SUP2\n",
    "PurchaseOrders.csv": "id,name,supplier_id,product_id,delivery_date,owner\nPO1,Northstar shipment,SUP1,BOX,2026-10-16,BUY\nPO2,Eastbank shipment,SUP2,TOOL,2026-10-17,BUY\n",
    "SalesOrders.csv": "id,name,product_id,purchase_order_id,required_date,quantity,owner\nSO1,Acme cartons,BOX,PO1,2026-10-19,10,CS\nSO2,Beacon cartons,BOX,PO1,2026-10-20,8,CS\nSO3,Later cartons,BOX,PO1,2026-10-28,5,CS\nSO4,Tape with stock,TAPE,PO1,2026-10-19,10,CS\nSO5,Unrelated tools,TOOL,PO2,2026-10-19,4,CS\n",
}
UPDATED = TABLES["PurchaseOrders.csv"].replace("2026-10-16", "2026-10-23")


async def seed(store, router, *, resume=False):
    existing = await store.get("profile", "profile")
    if existing and not (resume and existing.get("demo_fixture") == "harbor_supply"):
        raise ValueError("Load the demo into a new empty workspace")
    await store.put("profile", {**PROFILE, "demo_fixture": "harbor_supply"})
    await store.put("procedure", {"id": "demo_procedure", "text": PROFILE["procedure"], "version": 1, "approved": True, "active": True})
    for name, text in {**TABLES, "Company-guide.md": PROFILE["description"] + "\n\n" + PROFILE["procedure"]}.items():
        result = await preview(store, name, text.encode())
        job = await store.get("import", result["id"])
        mappings = [t["suggested_mapping"] for t in result["tables"]]
        await confirm(store, job, mappings, router)
    result = await preview(store, "PurchaseOrders.csv", UPDATED.encode())
    job = await store.get("import", result["id"])
    return await confirm(store, job, [t["suggested_mapping"] for t in result["tables"]], router)
