/// App shell: Gruvbox header, tab views, floating composer and nav rail.
library;

import 'package:material_ui/material_ui.dart';

import 'activity_view.dart';
import 'connect_pane.dart';
import 'dir_picker.dart';
import 'models.dart';
import 'navigation.dart';
import 'prompt_box.dart';
import 'run_screen.dart';
import 'session.dart';
import 'store.dart';
import 'task_list.dart';
import 'widgets.dart';
import 'workspace_view.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key, required this.store, this.saved});

  final LoopStore store;
  final ConnectionSettings? saved;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final TextEditingController _task = TextEditingController();
  bool _editingConnection = false;
  LoopTab _tab = LoopTab.tasks;

  @override
  void initState() {
    super.initState();
    _editingConnection = !widget.store.connected;
    final saved = widget.saved;
    if (saved != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && !widget.store.connected) {
          _connect(saved.host, saved.port, saved.token);
        }
      });
    }
  }

  @override
  void dispose() {
    _task.dispose();
    super.dispose();
  }

  Future<bool> _connect(String host, int port, String token) async {
    final ok = await widget.store.connect(host, port, token);
    if (ok) await Session.save(widget.store.settings!);
    if (!mounted) return ok;
    if (widget.store.connected) setState(() => _editingConnection = false);
    return ok;
  }

  Future<void> _submit() async {
    final ok = await widget.store.submitTask(_task.text);
    if (ok && mounted) _task.clear();
  }

  void _openRun(String runId) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => RunScreen(store: widget.store, runId: runId),
      ),
    );
  }

  void _browse() {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => DirPickerScreen(store: widget.store),
      ),
    );
  }

  Future<void> _disconnect() async {
    await Session.clear();
    widget.store.disconnect();
    if (mounted) setState(() => _editingConnection = true);
  }

  void _selectTab(LoopTab tab) {
    FocusManager.instance.primaryFocus?.unfocus();
    setState(() => _tab = tab);
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: widget.store,
      builder: (context, _) {
        final store = widget.store;
        final form = _editingConnection || !store.connected;
        if (form) {
          return Scaffold(
            body: SafeArea(
              child: LoopBackdrop(
                child: ConnectPane(
                  initial: store.settings,
                  error: store.error,
                  onConnect: _connect,
                  onCancel: store.connected
                      ? () => setState(() => _editingConnection = false)
                      : null,
                ),
              ),
            ),
          );
        }
        return _connected(store);
      },
    );
  }

  static Widget _shown(bool visible, Widget child) =>
      Visibility(visible: visible, child: child);

  Widget _connected(LoopStore store) {
    final keyboard = MediaQuery.viewInsetsOf(context).bottom > 0;
    final onTasks = _tab == LoopTab.tasks;
    return Scaffold(
      body: LoopBackdrop(
        child: SafeArea(
          bottom: false,
          child: Column(
            children: [
              // Stable child slots: a conditional `if` here would change the
              // Column list when the keyboard appears, rebuild the composer by
              // index and drop its focus before a key can land.
              _shown(
                !keyboard,
                LoopHeader(
                  state: store.statusState,
                  detail: store.statusDetail,
                  host: store.settings?.label,
                  onConfig: () => setState(() => _editingConnection = true),
                ),
              ),
              _shown(store.error != null, ErrorBanner(text: store.error ?? '')),
              Expanded(
                child: AnimatedSwitcher(
                  duration: const Duration(milliseconds: 240),
                  switchInCurve: Curves.easeOutCubic,
                  switchOutCurve: Curves.easeInCubic,
                  transitionBuilder: (child, animation) {
                    final offset = Tween<Offset>(
                      begin: const Offset(0.04, 0),
                      end: Offset.zero,
                    ).animate(animation);
                    return FadeTransition(
                      opacity: animation,
                      child: SlideTransition(position: offset, child: child),
                    );
                  },
                  child: KeyedSubtree(
                    key: ValueKey(_tab),
                    child: switch (_tab) {
                      LoopTab.tasks => TaskList(
                        store: store,
                        onBrowse: _browse,
                        onOpenRun: _openRun,
                      ),
                      LoopTab.activity => ActivityView(
                        store: store,
                        onOpenRun: _openRun,
                      ),
                      LoopTab.workspace => WorkspaceView(
                        store: store,
                        onBrowse: _browse,
                        onConfig: () =>
                            setState(() => _editingConnection = true),
                        onDisconnect: _disconnect,
                      ),
                    },
                  ),
                ),
              ),
              _shown(
                onTasks,
                PromptBox(
                  controller: _task,
                  canSubmit: store.canSubmit,
                  submitting: store.submitting,
                  onSubmit: _submit,
                  workspace: store.selectedRoot,
                ),
              ),
              _shown(
                !keyboard,
                FloatingNav(
                  active: _tab,
                  onSelect: _selectTab,
                  bottomInset: MediaQuery.paddingOf(context).bottom,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
