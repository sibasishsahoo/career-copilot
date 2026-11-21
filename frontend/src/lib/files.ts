// Mirrors the backend limits (backend/app/services/resume/extractor.py).
export const MAX_RESUME_BYTES = 5 * 1024 * 1024
export const ALLOWED_RESUME_EXTENSIONS = ['.pdf', '.docx'] as const

/** Returns a message if the file is unusable, or null if it is fine. Checking here avoids
 *  uploading a 50 MB file just to be told "too large". */
export function validateResumeFile(name: string, size: number): string | null {
  const lower = name.toLowerCase()
  if (!ALLOWED_RESUME_EXTENSIONS.some((extension) => lower.endsWith(extension))) {
    return 'Please choose a PDF or DOCX file.'
  }
  if (size === 0) return 'That file is empty.'
  if (size > MAX_RESUME_BYTES) return 'That file is larger than the 5 MB limit.'
  return null
}
