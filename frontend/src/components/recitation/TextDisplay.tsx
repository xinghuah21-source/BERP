interface TextDisplayProps {
  standardText: string
  currentProgress: number
}

export default function TextDisplay({ standardText }: TextDisplayProps) {
  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <h2 className="text-lg font-semibold mb-4">原文</h2>
      <div className="text-xl leading-10 whitespace-pre-wrap break-words text-gray-800">{standardText}</div>
    </div>
  )
}
