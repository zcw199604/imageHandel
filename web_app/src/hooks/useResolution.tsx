import { useCallback, useEffect, useState } from "react"

export type Resolution = "mobile" | "tablet" | "desktop"

export const MOBILE_BREAKPOINT = 768
export const TABLET_BREAKPOINT = 1224

const useResolution = () => {
  const getWindowWidth = () =>
    typeof window === "undefined" ? TABLET_BREAKPOINT : window.innerWidth

  const [width, setWidth] = useState(getWindowWidth)

  const windowSizeHandler = useCallback(() => {
    setWidth(window.innerWidth)
  }, [])

  useEffect(() => {
    window.addEventListener('resize', windowSizeHandler)

    return () => {
      window.removeEventListener('resize', windowSizeHandler)
    }
  }, [windowSizeHandler])

  if (width < MOBILE_BREAKPOINT) {
    return "mobile"
  }

  if (width >= MOBILE_BREAKPOINT && width < TABLET_BREAKPOINT) {
    return "tablet"
  }

  return "desktop"
}

export default useResolution
