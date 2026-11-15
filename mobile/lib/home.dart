/// Main screen: connection status, one scrollable task list and the fixed
/// bottom prompt. There is no tab or activity navigation.
library;

import 'package:material_ui/material_ui.dart';

import 'connect_pane.dart';
import 'dir_picker.dart';
import 'models.dart';
import 'prompt_box.dart';
import 'run_screen.dart';
import 'session.dart';
import 'store.dart';
import 'task_list.dart';
import 'widgets.dart';

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

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: widget.store,
      builder: (context, _) {
        final store = widget.store;
        final form = _editingConnection || !store.connected;
        return Scaffold(
          body: SafeArea(
            bottom: form,
            child: form
                ? ConnectPane(
                    initial: store.settings,
                    error: store.error,
                    onConnect: _connect,
                    onCancel: store.connected
                        ? () => setState(() => _editingConnection = false)
                        : null,
                  )
                : _body(store),
          ),
        );
      },
    );
  }

  Widget _body(LoopStore store) {
    return Column(
      children: [
        StatusBar(
          state: store.statusState,
          detail: store.statusDetail,
          trailing: TextButton(
            key: const Key('config-button'),
            onPressed: () => setState(() => _editingConnection = true),
            child: const Text('config'),
          ),
        ),
        if (store.error != null) ErrorBanner(text: store.error!),
        Expanded(
          child: TaskList(store: store, onBrowse: _browse, onOpenRun: _openRun),
        ),
        PromptBox(
          controller: _task,
          canSubmit: store.canSubmit,
          submitting: store.submitting,
          onSubmit: _submit,
        ),
      ],
    );
  }
}
