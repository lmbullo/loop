/// Fixed bottom task prompt: sharp edges, safe-area spacing and a multiline
/// field that grows before it scrolls.
library;

import 'package:material_ui/material_ui.dart';

import 'theme.dart';

class PromptBox extends StatelessWidget {
  const PromptBox({
    super.key,
    required this.controller,
    required this.canSubmit,
    required this.submitting,
    required this.onSubmit,
  });

  static const sideGap = 12.0;
  static const topGap = 8.0;
  static const bottomGap = 12.0;

  final TextEditingController controller;
  final bool canSubmit;
  final bool submitting;
  final VoidCallback onSubmit;

  @override
  Widget build(BuildContext context) {
    final inset = MediaQuery.paddingOf(context).bottom;
    return Padding(
      padding: EdgeInsets.fromLTRB(sideGap, topGap, sideGap, bottomGap + inset),
      child: Container(
        key: const Key('prompt-box'),
        decoration: const BoxDecoration(
          color: LoopColors.panel,
          border: Border.fromBorderSide(BorderSide(color: LoopColors.line)),
          borderRadius: BorderRadius.zero,
          boxShadow: [
            BoxShadow(
              color: Color(0x59000000),
              blurRadius: 16,
              offset: Offset(0, 4),
            ),
          ],
        ),
        child: Padding(
          padding: const EdgeInsets.all(10),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Expanded(
                child: TextField(
                  key: const Key('task-field'),
                  controller: controller,
                  minLines: 1,
                  maxLines: 3,
                  keyboardType: TextInputType.multiline,
                  textInputAction: TextInputAction.newline,
                  style: const TextStyle(
                    color: LoopColors.strong,
                    fontSize: 14,
                    height: 1.35,
                  ),
                  decoration: const InputDecoration(
                    hintText: 'task',
                    isDense: true,
                    contentPadding: EdgeInsets.symmetric(
                      horizontal: 10,
                      vertical: 10,
                    ),
                  ),
                  onSubmitted: (_) {
                    if (canSubmit) onSubmit();
                  },
                ),
              ),
              const SizedBox(width: 8),
              SizedBox(
                height: 40,
                child: FilledButton(
                  key: const Key('queue-button'),
                  onPressed: canSubmit ? onSubmit : null,
                  child: Text(submitting ? 'queueing' : 'queue'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
