export interface CourseContext {
  course_name?: string;
  program?: string;
  competencies?: string[];
}

export interface RewriteSectionRequest {
  section_heading?: string;
  current_text?: string;
  instruction: string;
  course_context?: CourseContext;
}

export interface RewriteSectionResponse {
  proposed_text: string;
  rationale: string;
}
