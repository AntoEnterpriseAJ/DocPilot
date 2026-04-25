import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { CaseStore } from '../case.store';

@Component({
  selector: 'app-chat-rail',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './chat-rail.component.html',
  styleUrl: './chat-rail.component.scss',
})
export class ChatRailComponent {
  protected readonly store = inject(CaseStore);
  protected readonly draft = signal('');
  protected readonly collapsed = signal(false);

  protected activeContextChip(): string | null {
    const tab = this.store.activeTab();
    if (!tab) return null;
    if (tab.body.kind === 'document') {
      const doc = this.store.documents().find(
        (d) => tab.body.kind === 'document' && d.id === tab.body.documentId,
      );
      return doc ? `@${doc.name}` : null;
    }
    return `@${tab.title} result`;
  }

  protected send(): void {
    const text = this.draft().trim();
    if (!text) return;
    const ctx = this.activeContextChip();
    this.store.appendChat({
      role: 'user',
      text,
      contextChips: ctx ? [ctx] : [],
    });
    this.draft.set('');
    // v1 stub assistant response so the loop feels alive.
    setTimeout(() => {
      this.store.appendChat({
        role: 'assistant',
        text: 'Connect your Anthropic key to enable real responses. (stub)',
      });
    }, 400);
  }

  protected quickAction(kind: 'explain' | 'improve' | 'summarize'): void {
    const map = {
      explain: 'Explain the active document in plain language.',
      improve: 'Suggest improvements for the active document.',
      summarize: 'Summarize the active document.',
    };
    this.draft.set(map[kind]);
  }

  protected onKey(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.send();
    }
  }

  protected toggleCollapse(): void {
    this.collapsed.update((c) => !c);
  }
}
