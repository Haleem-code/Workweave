import { request as httpRequest } from 'node:http'
import { request as httpsRequest } from 'node:https'
import { Readable } from 'node:stream'
export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'
// Node HTTP preserves Host explicitly; fetch may replace it with the API destination.
async function proxy(request: Request) {
  const incoming = new URL(request.url)
  const backend = process.env.API_URL || (process.env.NODE_ENV === 'development' ? 'http://127.0.0.1:8088' : 'http://api:8000')
  const target = new URL(incoming.pathname + incoming.search, backend)
  const headers: Record<string,string> = Object.fromEntries(request.headers)
  for (const key of ['connection','transfer-encoding','content-length','accept-encoding']) delete headers[key]
  if (!headers.host) return Response.json({detail:'Missing request host'}, {status:400})
  const body = ['GET','HEAD'].includes(request.method) ? undefined : Buffer.from(await request.arrayBuffer())
  if (body) headers['content-length'] = String(body.length)
  try {
    return await new Promise<Response>((resolve,reject) => {
      const upstream = (target.protocol === 'https:' ? httpsRequest : httpRequest)(target, {
        method:request.method, headers, signal:request.signal
      }, response => {
        const result = new Headers()
        for (const [key,value] of Object.entries(response.headers)) {
          if (!value || ['connection','transfer-encoding','content-length','content-encoding'].includes(key)) continue
          for (const item of Array.isArray(value) ? value : [value]) result.append(key,item)
        }
        result.set('Cache-Control','no-store')
        const status = response.statusCode || 502
        const stream = request.method === 'HEAD' || [204,304].includes(status) ? null : (Readable.toWeb(response) as unknown as ReadableStream<Uint8Array>)
        resolve(new Response(stream,{status,headers:result}))
      })
      upstream.on('error',reject)
      upstream.end(body)
    })
  } catch {
    return Response.json({detail:'The Workweave API is unavailable. Check the local service and retry.'},{status:502})
  }
}
export { proxy as GET, proxy as POST, proxy as PUT, proxy as PATCH, proxy as DELETE, proxy as OPTIONS, proxy as HEAD }