import { describe, expect, it } from 'vitest'
import { MAX_RESUME_BYTES, validateResumeFile } from './files'

describe('validateResumeFile', () => {
  it('accepts a PDF and a DOCX', () => {
    expect(validateResumeFile('resume.pdf', 1000)).toBeNull()
    expect(validateResumeFile('resume.docx', 1000)).toBeNull()
  })

  it('ignores letter case in the extension', () => {
    expect(validateResumeFile('RESUME.PDF', 1000)).toBeNull()
  })

  it('rejects other file types', () => {
    expect(validateResumeFile('resume.txt', 1000)).toBe('Please choose a PDF or DOCX file.')
    expect(validateResumeFile('resume', 1000)).toBe('Please choose a PDF or DOCX file.')
    expect(validateResumeFile('photo.png', 1000)).toBe('Please choose a PDF or DOCX file.')
  })

  it('rejects an empty file', () => {
    expect(validateResumeFile('resume.pdf', 0)).toBe('That file is empty.')
  })

  it('accepts a file exactly at the limit and rejects one byte over', () => {
    expect(validateResumeFile('resume.pdf', MAX_RESUME_BYTES)).toBeNull()
    expect(validateResumeFile('resume.pdf', MAX_RESUME_BYTES + 1)).toBe('That file is larger than the 5 MB limit.')
  })
})
