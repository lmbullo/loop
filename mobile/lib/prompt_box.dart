/// Floating task composer: one rounded Gruvbox surface that clears the
/// keyboard and sits above the floating navigation rail.
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
    this.workspace,
  });

  static const sideGap = 16.0;
  static const topGap = 8.0;
  static const bottomGap = 10.0;

  final TextEditingController controller;
  final bool canSubmit;
  final bool submitting;
  final VoidCallback onSubmit;
  final String? workspace;

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
    return 'enter to queue';
  }

  @override
  Widget build(BuildContext context) {
    final accent = _focused && widget.canSubmit;
    final hintColor = accent ? LoopColors.accent : LoopColors.faint;
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        PromptBox.sideGap,
        PromptBox.topGap,
        PromptBox.sideGap,
        PromptBox.bottomGap,
      ),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        curve: Curves.easeOut,
        key: const Key('prompt-box'),
        decoration: BoxDecoration(
          color: LoopColors.surface,
          borderRadius: BorderRadius.circular(LoopRadius.xl),
          border: Border.all(
            color: accent ? LoopColors.accent : LoopColors.lineStrong,
            width: accent ? 1.4 : 1,
          ),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.3),
              blurRadius: 24,
              offset: const Offset(0, 10),
            ),
            if (accent)
              BoxShadow(
                color: LoopColors.accent.withValues(alpha: 0.12),
                blurRadius: 26,
                offset: const Offset(0, 2),
              ),
          ],
        ),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(14, 9, 10, 10),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Row(
                children: [
                  Icon(
                    Icons.auto_awesome_rounded,
                    size: 13,
                    color: accent ? LoopColors.accent : LoopColors.faint,
                  ),
                  const SizedBox(width: 6),
                  Text(
                    'compose',
                    style: LoopType.label.copyWith(
                      fontSize: 9.5,
                      color: accent ? LoopColors.accent : LoopColors.muted,
                    ),
                  ),
                  const SizedBox(width: LoopSpace.sm),
                  Expanded(
                    child: Text(
                      widget.workspace == null
                          ? ''
                          : _basename(widget.workspace!),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: LoopType.caption.copyWith(
                        color: LoopColors.faint,
                        letterSpacing: 0.2,
                      ),
                    ),
                  ),
                  Flexible(
                    child: Text(
                      _hint,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: LoopType.caption.copyWith(color: hintColor),
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
                        hintText: 'describe a task…',
                        filled: false,
                        isDense: true,
                        border: InputBorder.none,
                        enabledBorder: InputBorder.none,
                        focusedBorder: InputBorder.none,
                        contentPadding: EdgeInsets.only(top: 8, bottom: 6),
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
                  const SizedBox(width: LoopSpace.sm),
                  Semantics(
                    button: true,
                    label: widget.submitting ? 'queueing task' : 'queue task',
                    child: SizedBox(
                      width: 46,
                      height: 46,
                      child: FilledButton(
                        key: const Key('queue-button'),
                        onPressed: widget.canSubmit ? widget.onSubmit : null,
                        style: FilledButton.styleFrom(
                          padding: EdgeInsets.zero,
                          minimumSize: const Size(46, 46),
                          tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                          backgroundColor: LoopColors.accent,
                          foregroundColor: LoopColors.bg0Hard,
                          disabledBackgroundColor: LoopColors.line,
                          disabledForegroundColor: LoopColors.faint,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(LoopRadius.md),
                          ),
                        ),
                        child: widget.submitting
                            ? const SizedBox(
                                width: 16,
                                height: 16,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  color: LoopColors.bg0Hard,
                                ),
                              )
                            : const Icon(Icons.arrow_upward_rounded, size: 21),
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

  static String _basename(String path) {
    final clean = path.endsWith('/')
        ? path.substring(0, path.length - 1)
        : path;
    final index = clean.lastIndexOf('/');
    return index < 0 ? clean : clean.substring(index + 1);
  }
}
