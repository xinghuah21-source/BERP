import Modal from './Modal'

export default function ConfirmModal({
  open,
  title,
  message,
  detail,
  confirmText = '确认删除',
  cancelText = '取消',
  onConfirm,
  onClose,
}: {
  open: boolean
  title: string
  message: string
  detail?: string
  confirmText?: string
  cancelText?: string
  onConfirm: () => void
  onClose: () => void
}) {
  return (
    <Modal title={title} open={open} onClose={onClose}>
      <div className="space-y-3">
        <div>{message}</div>
        {detail && <div className="text-sm text-gray-500">{detail}</div>}
        <div className="flex justify-end gap-3 pt-2">
          <button onClick={onClose} className="px-4 py-2 rounded-md border hover:bg-gray-50">
            {cancelText}
          </button>
          <button onClick={onConfirm} className="px-4 py-2 rounded-md bg-red-600 text-white hover:bg-red-700">
            {confirmText}
          </button>
        </div>
      </div>
    </Modal>
  )
}

