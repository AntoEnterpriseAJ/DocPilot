import { CommonModule } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { RewriteSectionResponse } from '../models/copilot.models';
import { CopilotService } from '../services/copilot.service';

interface HistoryEntry {
  instruction: string;
  proposed_text: string;
  rationale: string;
}

@Component({
  selector: 'app-copilot-page',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './copilot-page.component.html',
  styleUrls: ['./copilot-page.component.scss'],
})
export class CopilotPageComponent {
  private readonly service = inject(CopilotService);

  readonly heading = signal<string>('');
  readonly currentText = signal<string>('');
  readonly instruction = signal<string>('');
  readonly courseName = signal<string>('');
  readonly competencies = signal<string>('');

  readonly loading = signal(false);
  readonly errorMessage = signal<string | null>(null);
  readonly proposal = signal<RewriteSectionResponse | null>(null);
  readonly history = signal<HistoryEntry[]>([]);

  canGenerate(): boolean {
    return !this.loading() && this.instruction().trim().length > 0;
  }

  generate(): void {
    if (!this.canGenerate()) return;
    const competencies = this.competencies()
      .split('\n')
      .map((s) => s.trim())
      .filter(Boolean);
    this.loading.set(true);
    this.errorMessage.set(null);
    this.service
      .rewriteSection({
        section_heading: this.heading() || undefined,
        current_text: this.currentText() || undefined,
        instruction: this.instruction(),
        course_context: this.courseName() || competencies.length
          ? {
              course_name: this.courseName() || undefined,
              competencies,
            }
          : undefined,
      })
      .subscribe({
        next: (resp) => {
          this.proposal.set(resp);
          this.loading.set(false);
        },
        error: (err) => {
          this.errorMessage.set(
            err?.error?.detail ?? err?.message ?? 'Copilot request failed',
          );
          this.loading.set(false);
        },
      });
  }

  accept(): void {
    const p = this.proposal();
    if (!p) return;
    this.history.update((h) => [
      ...h,
      { instruction: this.instruction(), ...p },
    ]);
    this.currentText.set(p.proposed_text);
    this.proposal.set(null);
    this.instruction.set('');
  }

  refine(): void {
    const p = this.proposal();
    if (!p) return;
    // Treat the proposal as the new starting point and let the user
    // give a follow-up instruction.
    this.currentText.set(p.proposed_text);
    this.history.update((h) => [
      ...h,
      { instruction: this.instruction(), ...p },
    ]);
    this.proposal.set(null);
    this.instruction.set('');
  }

  discard(): void {
    this.proposal.set(null);
  }
}
