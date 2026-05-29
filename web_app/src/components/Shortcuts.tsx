import { Keyboard } from "lucide-react"
import { IconButton } from "@/components/ui/button"
import { useToggle } from "@uidotdev/usehooks"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "./ui/dialog"
import useHotKey from "@/hooks/useHotkey"

interface ShortcutProps {
  content: string
  keys: string[]
}

function ShortCut(props: ShortcutProps) {
  const { content, keys } = props

  return (
    <div className="flex justify-between gap-4">
      <div>{content}</div>
      <div className="flex gap-[8px]">
        {keys.map((k) => (
          // TODO: 优化快捷键显示
          <div className="border px-2 py-1 rounded-lg" key={k}>
            {k}
          </div>
        ))}
      </div>
    </div>
  )
}

const isMac = function () {
  return /macintosh|mac os x/i.test(navigator.userAgent)
}

const CmdOrCtrl = () => {
  return isMac() ? "Cmd" : "Ctrl"
}

export function Shortcuts() {
  const [open, toggleOpen] = useToggle(false)

  useHotKey("h", () => {
    toggleOpen()
  })

  return (
    <Dialog open={open} onOpenChange={toggleOpen}>
      <DialogTrigger asChild>
        <IconButton tooltip="快捷键">
          <Keyboard />
        </IconButton>
      </DialogTrigger>
      <DialogContent className="max-w-[calc(100vw-1rem)]">
        <DialogHeader>
          <DialogTitle>快捷键</DialogTitle>
          <div className="flex gap-2 flex-col pt-4">
            <ShortCut content="平移" keys={["空格 + 拖动"]} />
            <ShortCut content="重置缩放/平移" keys={["Esc"]} />
            <ShortCut content="减小画笔" keys={["["]} />
            <ShortCut content="增大画笔" keys={["]"]} />
            <ShortCut content="查看原图" keys={["按住 Tab"]} />

            <ShortCut content="撤销" keys={[CmdOrCtrl(), "Z"]} />
            <ShortCut content="重做" keys={[CmdOrCtrl(), "Shift", "Z"]} />
            <ShortCut content="复制结果" keys={[CmdOrCtrl(), "C"]} />
            <ShortCut content="粘贴图片" keys={[CmdOrCtrl(), "V"]} />
            <ShortCut
              content="手动触发修复"
              keys={["Shift", "R"]}
            />
            <ShortCut content="打开/关闭快捷键" keys={["H"]} />
            <ShortCut content="打开/关闭设置" keys={["S"]} />
            <ShortCut content="打开/关闭文件管理" keys={["F"]} />
          </div>
        </DialogHeader>
      </DialogContent>
    </Dialog>
  )
}

export default Shortcuts
