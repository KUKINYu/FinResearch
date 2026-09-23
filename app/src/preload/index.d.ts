/** 预加载桥的类型声明（renderer 可见） */
export interface FinEngineBridge {
  health(): Promise<{ status: string; version?: string }>
  info(): Promise<Record<string, unknown> | null>
}

declare global {
  interface Window {
    finengine: FinEngineBridge
  }
}
