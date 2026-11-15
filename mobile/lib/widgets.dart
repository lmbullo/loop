/// Small shared rows that keep every screen on the same terminal-like grid.
library;

import 'package:material_ui/material_ui.dart';

import 'theme.dart';

class StatusBar extends StatelessWidget {
  const StatusBar({
    super.key,
    required this.state,
    required this.detail,
    this.trailing,
  });

  final String state;
  final String detail;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    final color = state == 'running' ? LoopColors.ok : LoopColors.error;
    return Container(
      padding: const EdgeInsets.fromLTRB(12, 10, 8, 8),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: LoopColors.line)),
      ),
      child: Row(
        children: [
          Text(statusGlyph(state), style: TextStyle(color: color)),
          const SizedBox(width: 8),
          Expanded(
            flex: 2,
            child: Text(
              'daemon $state',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(color: LoopColors.strong),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            flex: 3,
            child: Text(
              detail,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(color: LoopColors.muted, fontSize: 12),
            ),
          ),
          if (trailing != null) trailing!,
        ],
      ),
    );
  }
}

class ErrorBanner extends StatelessWidget {
  const ErrorBanner({super.key, required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      color: LoopColors.error.withValues(alpha: 0.12),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      child: Text(
        '✕ $text',
        style: const TextStyle(color: LoopColors.error, fontSize: 12),
      ),
    );
  }
}

class SectionHeader extends StatelessWidget {
  const SectionHeader({super.key, required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 18, 16, 8),
      child: Text(
        label,
        style: const TextStyle(
          color: LoopColors.muted,
          fontSize: 12,
          letterSpacing: 0.6,
        ),
      ),
    );
  }
}

class EmptyLine extends StatelessWidget {
  const EmptyLine({super.key, required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 6, 16, 8),
      child: Text(text, style: const TextStyle(color: LoopColors.muted)),
    );
  }
}
