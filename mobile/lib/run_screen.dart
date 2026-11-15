/// One run: live tool calls plus the untruncated final summary.
library;

import 'package:material_ui/material_ui.dart';

import 'models.dart';
import 'store.dart';
import 'theme.dart';
import 'widgets.dart';

class RunScreen extends StatefulWidget {
  const RunScreen({super.key, required this.store, required this.runId});

  final LoopStore store;
  final String runId;

  @override
  State<RunScreen> createState() => _RunScreenState();
}

class _RunScreenState extends State<RunScreen> {
  final ScrollController _scroll = ScrollController();
  int _lastCount = 0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) widget.store.watchRun(widget.runId);
    });
  }

  @override
  void dispose() {
    widget.store.unwatchRun(widget.runId);
    _scroll.dispose();
    super.dispose();
  }

  void _follow(int count) {
    if (count == _lastCount) return;
    _lastCount = count;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scroll.hasClients) return;
      _scroll.animateTo(
        _scroll.position.maxScrollExtent,
        duration: const Duration(milliseconds: 140),
        curve: Curves.easeOut,
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: widget.store,
      builder: (context, _) {
        final store = widget.store;
        final log = store.runLog;
        final current = store.snapshot.current;
        final live = current?.runId == widget.runId ? current!.state : null;
        final state = live ?? log?.state ?? 'running';
        final id = log?.id.isNotEmpty == true ? log!.id : widget.runId;
        final calls = log?.callCount ?? 0;
        _follow(log?.entries.length ?? 0);
        return Scaffold(
          appBar: AppBar(
            title: const Text('run log'),
            actions: [
              Padding(
                padding: const EdgeInsets.only(right: LoopSpace.lg),
                child: StateChip(state: state),
              ),
            ],
          ),
          body: LoopBackdrop(
            child: SafeArea(
              top: false,
              child: Column(
                children: [
                  _MetaBar(
                    state: state,
                    text:
                        'id=${_short(id)} · state=$state · '
                        'turns=${log?.turns ?? 0} · calls=$calls',
                    terminal: log?.terminal == true,
                  ),
                  if (store.error != null) ErrorBanner(text: store.error!),
                  Expanded(child: _entries(store, log)),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _entries(LoopStore store, RunLog? log) {
    if (log == null) {
      return Center(
        child: Text(
          store.loadingLog ? 'loading log…' : 'log unavailable',
          style: LoopType.meta.copyWith(color: LoopColors.faint),
        ),
      );
    }
    if (log.entries.isEmpty) {
      return const Center(
        child: EmptyState(
          icon: Icons.hourglass_empty_rounded,
          title: 'waiting for events',
          body: 'The agent will stream tool calls here as soon as it starts.',
        ),
      );
    }
    return SelectionArea(
      child: ListView.builder(
        controller: _scroll,
        padding: const EdgeInsets.only(
          top: LoopSpace.sm,
          bottom: LoopSpace.xxl,
        ),
        itemCount: log.entries.length,
        itemBuilder: (context, index) => _EntryView(entry: log.entries[index]),
      ),
    );
  }

  static String _short(String value) =>
      value.length <= 12 ? value : '…${value.substring(value.length - 8)}';
}

class _MetaBar extends StatelessWidget {
  const _MetaBar({
    required this.state,
    required this.text,
    required this.terminal,
  });

  final String state;
  final String text;
  final bool terminal;

  @override
  Widget build(BuildContext context) {
    final tone = statusColor(state);
    return Container(
      margin: const EdgeInsets.fromLTRB(
        LoopSpace.lg,
        LoopSpace.xs,
        LoopSpace.lg,
        LoopSpace.xs,
      ),
      padding: const EdgeInsets.fromLTRB(13, 11, 12, 11),
      decoration: BoxDecoration(
        color: LoopColors.surface,
        borderRadius: BorderRadius.circular(LoopRadius.md),
        border: Border.all(color: tone.withValues(alpha: 0.28)),
      ),
      child: Row(
        children: [
          Container(
            width: 28,
            height: 28,
            decoration: BoxDecoration(
              color: tone.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(LoopRadius.sm),
            ),
            child: Icon(statusIcon(state), color: tone, size: 16),
          ),
          const SizedBox(width: LoopSpace.sm),
          Expanded(
            child: Text(
              text,
              style: LoopType.meta.copyWith(fontSize: 11),
              overflow: TextOverflow.ellipsis,
            ),
          ),
          if (terminal)
            Container(
              padding: const EdgeInsets.fromLTRB(7, 4, 8, 4),
              decoration: BoxDecoration(
                color: LoopColors.ok.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(LoopRadius.pill),
              ),
              child: const Text(
                'terminal',
                style: TextStyle(
                  color: LoopColors.ok,
                  fontSize: 9.5,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 0.4,
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _EntryView extends StatelessWidget {
  const _EntryView({required this.entry});

  final LogEntry entry;

  @override
  Widget build(BuildContext context) {
    if (entry.isCall) return _call();
    if (entry.isResult) return _result();
    if (entry.kind == 'interrupted') {
      return _message(
        'interrupted',
        LoopColors.warn,
        entry.reason,
        Icons.pause_circle_filled_rounded,
      );
    }
    if (entry.kind == 'error') {
      return _message(
        'error',
        LoopColors.error,
        entry.text.isEmpty ? entry.finish : entry.text,
        Icons.error_rounded,
      );
    }
    if (entry.kind == 'torn') {
      return _message(
        'torn',
        LoopColors.warn,
        entry.text,
        Icons.warning_amber_rounded,
      );
    }
    return _message(
      'pending',
      LoopColors.info,
      entry.text.isEmpty ? 'summary pending' : entry.text,
      Icons.schedule_rounded,
    );
  }

  Widget _call() {
    final args = entry.args.isEmpty ? '' : ' — ${entry.args}';
    final tone = entry.failed ? LoopColors.error : LoopColors.aqua;
    return Container(
      margin: const EdgeInsets.fromLTRB(
        LoopSpace.lg,
        LoopSpace.xs,
        LoopSpace.lg,
        LoopSpace.xs,
      ),
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
      decoration: BoxDecoration(
        color: LoopColors.surface.withValues(alpha: 0.72),
        borderRadius: BorderRadius.circular(LoopRadius.md),
        border: Border.all(color: LoopColors.line),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(Icons.terminal_rounded, size: 15, color: tone),
              const SizedBox(width: LoopSpace.sm),
              Expanded(
                child: Text.rich(
                  TextSpan(
                    style: LoopType.body.copyWith(fontSize: 12.5, height: 1.45),
                    children: [
                      const TextSpan(
                        text: '▸ ',
                        style: TextStyle(color: LoopColors.faint),
                      ),
                      TextSpan(
                        text: 't${entry.turn} ',
                        style: const TextStyle(color: LoopColors.faint),
                      ),
                      TextSpan(
                        text: entry.name.isEmpty ? '?' : entry.name,
                        style: const TextStyle(
                          color: LoopColors.strong,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      TextSpan(
                        text: args,
                        style: const TextStyle(color: LoopColors.body),
                      ),
                    ],
                  ),
                  maxLines: 4,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
          if (entry.obs.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 6, left: 2),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(
                    Icons.subdirectory_arrow_right_rounded,
                    size: 14,
                    color: entry.failed ? LoopColors.error : LoopColors.faint,
                  ),
                  const SizedBox(width: 4),
                  Expanded(
                    child: Text(
                      entry.obs,
                      style: TextStyle(
                        color: entry.failed
                            ? LoopColors.error
                            : LoopColors.muted,
                        fontSize: 11.5,
                        height: 1.45,
                      ),
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _result() {
    final body = entry.result.isEmpty ? 'finish=${entry.finish}' : entry.result;
    return _Callout(
      color: LoopColors.ok,
      icon: Icons.check_circle_rounded,
      head: '✓ result',
      note: entry.finish,
      body: body,
    );
  }

  Widget _message(String head, Color color, String body, IconData icon) {
    return _Callout(color: color, icon: icon, head: head, body: body);
  }
}

class _Callout extends StatelessWidget {
  const _Callout({
    required this.color,
    required this.icon,
    required this.head,
    this.note = '',
    this.body = '',
  });

  final Color color;
  final IconData icon;
  final String head;
  final String note;
  final String body;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.fromLTRB(
        LoopSpace.lg,
        LoopSpace.sm,
        LoopSpace.lg,
        LoopSpace.sm,
      ),
      padding: const EdgeInsets.fromLTRB(13, 12, 13, 13),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.07),
        borderRadius: BorderRadius.circular(LoopRadius.lg),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: color, size: 17),
              const SizedBox(width: 6),
              Text(
                head,
                style: TextStyle(
                  color: color,
                  fontSize: 12.5,
                  fontWeight: FontWeight.w600,
                  height: 1.2,
                ),
              ),
              if (note.isNotEmpty) ...[
                const Spacer(),
                Text(
                  note,
                  style: LoopType.caption.copyWith(color: LoopColors.muted),
                ),
              ],
            ],
          ),
          if (body.isNotEmpty) ...[
            const SizedBox(height: LoopSpace.sm),
            Text(
              body,
              style: LoopType.body.copyWith(fontSize: 13, height: 1.55),
            ),
          ],
        ],
      ),
    );
  }
}
