import * as React from "react"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"

interface ReportDialogProps {
  type: "create" | "edit"
  open: boolean
  onOpenChange: (open: boolean) => void
  report?: {
    id?: string
    title: string
    content: string
    author: {
      name: string
      avatar?: string
    }
    date: string
  }
  onSave?: (data: any) => void
  onDelete?: () => void
}

export function ReportDialog({
  type,
  open,
  onOpenChange,
  report,
  onSave,
  onDelete,
}: ReportDialogProps) {
  const [title, setTitle] = React.useState(report?.title ?? "")
  const [content, setContent] = React.useState(report?.content ?? "")
  const [isSaving, setIsSaving] = React.useState(false)

  React.useEffect(() => {
    const saveTimeout = setTimeout(() => {
      if (title || content) {
        onSave?.({
          title,
          content,
          date: new Date().toISOString(),
        })
      }
    }, 1000)

    return () => clearTimeout(saveTimeout)
  }, [title, content, onSave])

  const handleSave = React.useCallback(() => {
    setIsSaving(true)
    onSave?.({
      title,
      content,
      date: new Date().toISOString(),
    })
    setIsSaving(false)
    onOpenChange(false)
  }, [title, content, onSave, onOpenChange])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-[500px]"
        aria-describedby="report-dialog-description"
      >
        <DialogHeader>
          <DialogTitle>
            {type === "create" ? "Create New Report" : "Edit Report"}
          </DialogTitle>
          <p id="report-dialog-description" className="text-sm text-muted-foreground">
            {type === "create"
              ? "Create a new report by filling out the form below."
              : "Edit your existing report using the form below."}
          </p>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label htmlFor="title">Title</Label>
            <Input
              id="title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Report title"
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="content">Content</Label>
            <Textarea
              id="content"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Write your report content here..."
              className="min-h-[200px]"
            />
          </div>
        </div>
        <DialogFooter className="gap-2">
          {type === "edit" && (
            <Button
              variant="destructive"
              onClick={onDelete}
              className="mr-auto"
            >
              Delete
            </Button>
          )}
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={isSaving}>
            {isSaving ? "Saving..." : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
