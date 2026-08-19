/** 媒体资源地址规范化工具。
 *
 * 历史版本曾把家具图序列化成带 Host 的绝对地址（如
 * http://localhost:8000/media/...），该地址在 App / 内网 / HTTPS 环境下会失效。
 * 这里把以 /media/ 开头的绝对地址统一降回站点相对路径，交由浏览器按当前
 * 访问域名解析；其他 URL 原样返回。
 */
export function resolveMediaUrl(value) {
  if (!value) return null
  const text = String(value)
  const matched = text.match(/^https?:\/\/[^/]+(\/media\/.*)$/i)
  return matched ? matched[1] : text
}