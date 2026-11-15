/// Fixed bottom prompt: a single docked surface with one hairline edge.
///
/// The field is borderless and transparent; the only box is the prompt surface
/// itself, so there is no panel inside a panel.
library;

import 'package:material_ui/material_ui.dart';

import 'theme.dart';

class PromptBox extends StatefulWidget {
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
  State<PromptBox> createState() => _PromptBoxState();
}

class _PromptBoxState extends State<PromptBox> {
  final FocusNode _focus = FocusNode();
  bool _focused = false;

  @override
  void initState() {
    super.initState();
    _focus.addListener(_onFocus);
  }

  @override
  void dispose() {
    _focus.removeListener(_onFocus);
    _focus.dispose();
    super.dispose();
  }

  void _onFocus() {
    if (_focused != _focus.hasFocus) {
      setState(() => _focused = _focus.hasFocus);
    }
  }

  String get _hint {
    if (widget.submitting) return 'queueing';
    if (!widget.canSubmit) return 'select workspace';
    return 'queue';
  }

  @override
  Widget build(BuildContext context) {
    final inset = MediaQuery.paddingOf(context).bottom;
    final hintColor = _focused && widget.canSubmit
        ? LoopColors.accent
        : LoopColors.faint;
    return Padding(
      padding: EdgeInsets.fromLTRB(
        PromptBox.sideGap,
        PromptBox.topGap,
        PromptBox.sideGap,
        PromptBox.bottomGap + inset,
      ),
      child: Container(
        key: const Key('prompt-box'),
        decoration: const BoxDecoration(
          color: LoopColors.panel,
          borderRadius: BorderRadius.zero,
          boxShadow: [
            BoxShadow(
              color: Color(0x40000000),
              blurRadius: 20,
              offset: Offset(0, -4),
            ),
          ],
        ),
        foregroundDecoration: BoxDecoration(
          border: Border(
            top: BorderSide(
              color: _focused ? LoopColors.accent : LoopColors.lineStrong,
            ),
          ),
        ),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(14, 7, LoopSpace.sm, 7),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Row(
                children: [
                  const Text('prompt', style: LoopType.label),
                  const Spacer(),
                  Text(
                    _hint,
                    style: LoopType.label.copyWith(
                      color: hintColor,
                      fontSize: 10,
                    ),
                  ),
                  const SizedBox(width: LoopSpace.sm),
                ],
              ),
              Row(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Expanded(
                    child: TextField(
                      key: const Key('task-field'),
                      controller: widget.controller,
                      focusNode: _focus,
                      minLines: 1,
                      maxLines: 3,
                      keyboardType: TextInputType.multiline,
                      keyboardAppearance: Brightness.dark,
                      textInputAction: TextInputAction.newline,
                      textCapitalization: TextCapitalization.sentences,
                      cursorColor: LoopColors.accent,
                      style: LoopType.task.copyWith(fontSize: 14),
                      decoration: const InputDecoration(
                        hintText: 'describe a task',
                        isDense: true,
                        border: InputBorder.none,
                        enabledBorder: InputBorder.none,
                        focusedBorder: InputBorder.none,
                        contentPadding: EdgeInsets.zero,
                        hintStyle: TextStyle(
                          color: LoopColors.faint,
                          fontSize: 14,
                        ),
                      ),
                      onSubmitted: (_) {
                        if (widget.canSubmit) widget.onSubmit();
                      },
                    ),
                  ),
                  const SizedBox(width: 6),
                  Semantics(
                    button: true,
                    label: widget.submitting ? 'queueing task' : 'queue task',
                    child: SizedBox(
                      width: 44,
                      height: 40,
                      child: TextButton(
                        key: const Key('queue-button'),
                        onPressed: widget.canSubmit ? widget.onSubmit : null,
                        style: TextButton.styleFrom(
                          padding: EdgeInsets.zero,
                          minimumSize: const Size(44, 40),
                          tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                          backgroundColor: Colors.transparent,
                          foregroundColor: LoopColors.accent,
                          disabledForegroundColor: LoopColors.faint,
                          shape: const RoundedRectangleBorder(
                            borderRadius: BorderRadius.zero,
                          ),
                        ),
                        child: Text(
                          widget.submitting ? '…' : '↵',
                          style: const TextStyle(fontSize: 18, height: 1),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
