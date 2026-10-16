import { Check } from 'lucide-react'
import { Mapping, Preview } from '../api'

const fields = ['name', 'supplier_id', 'product_id', 'purchase_order_id', 'delivery_date', 'required_date', 'quantity', 'stock', 'owner', 'status']
const kinds = ['BusinessRecord', 'Supplier', 'Product', 'PurchaseOrder', 'SalesOrder', 'Team']

export function ImportReview({ preview, mappings, onChange, onConfirm, busy }: { preview: Preview; mappings: Mapping[]; onChange: (mappings: Mapping[]) => void; onConfirm: () => void; busy: boolean }) {
  return <article className="ww-import-preview"><div className="panel-heading"><div><h3>{preview.filename}</h3><p>Parsed · waiting for your review</p></div><span className="badge needs_review">Review</span></div>
    {preview.warnings.map(w => <p className="ww-warning" key={w}>{w}</p>)}
    {preview.sections.map((s, i) => <blockquote key={i}><small>{s.location}</small>{s.text}</blockquote>)}
    {preview.tables.map((table, index) => {
      const mapping = mappings[index] || table.suggested_mapping
      const change = (patch: Partial<Mapping>) => onChange(mappings.map((m, i) => i === index ? { ...m, ...patch } : m))
      return <div className="mapping" key={table.name}><h3>{table.name} <small>· {table.row_count} rows</small></h3><div className="mapping-controls"><label>Record type<select disabled={busy} value={mapping.entity_type} onChange={e => change({ entity_type: e.target.value })}>{kinds.map(kind => <option key={kind}>{kind}</option>)}</select></label><label>Unique identifier<select disabled={busy} value={mapping.key_column} onChange={e => change({ key_column: e.target.value })}>{table.headers.map(header => <option key={header}>{header}</option>)}</select></label></div><div className="table-scroll"><table><thead><tr>{table.headers.map(header => <th key={header}>{header}</th>)}</tr></thead><tbody>{table.rows.map((row, i) => <tr key={i}>{row.map((value, j) => <td key={j}>{value}</td>)}</tr>)}</tbody></table></div><details><summary>Review column meanings</summary><div className="field-grid">{fields.map(field => <label key={field}>{field.replaceAll('_', ' ')}<select disabled={busy} value={mapping.fields[field] || ''} onChange={e => { const next = { ...mapping.fields }; if (e.target.value) next[field] = e.target.value; else delete next[field]; change({ fields: next }) }}><option value="">Not provided</option>{table.headers.map(header => <option key={header}>{header}</option>)}</select></label>)}</div></details></div>
    })}<button className="primary" disabled={busy} onClick={onConfirm}>Confirm & import <Check size={15} /></button>
  </article>
}
