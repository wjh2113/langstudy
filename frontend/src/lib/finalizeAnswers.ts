/** 等识别成功或失败后固定评分输入，避免报告与随后变化的作答不一致。 */
export async function finalizeAnswers<T>(pending: Iterable<Promise<unknown>>, read: () => T): Promise<T> {
  await Promise.allSettled([...pending])
  // 与接口一致地序列化；作答中的发音评测对象可能仍是 Vue Proxy。
  return JSON.parse(JSON.stringify(read())) as T
}
