import 'package:loop_mobile/api.dart';

class FakeApi implements LoopApi {
  Map<String, dynamic> snapshotData = {
    'daemon': {'state': 'running'},
    'current': null,
    'queue': [],
    'done': [],
    'costs': {'total': 0},
  };
  Map<String, dynamic> dirsData = {
    'path': null,
    'roots': [
      {'name': 'ws', 'path': '/tmp/ws'}
    ],
    'dirs': [],
  };
  Map<String, dynamic> workspacesData = {
    'workspaces': [
      {
        'name': 'ws',
        'path': '/tmp/ws',
        'state': 'running',
        'running': 0,
        'queued': 0,
        'done': 0,
        'cost': 0,
      }
    ],
    'totals': {'cost': 0},
  };
  final List<String?> snapshotRoots = [];
  final List<String> started = [];
  String? failedRoot;
  final Map<String, Map<String, dynamic>> listings = {};
  Map<String, dynamic> logData = {
    'id': 'run-1',
    'state': 'running',
    'turns': 1,
    'terminal': false,
    'entries': [
      {'kind': 'call', 'turn': 1, 'name': 'exec', 'args': '[]', 'obs': 'ok'}
    ],
  };
  Object? failWith;
  int snapshots = 0;
  int logs = 0;
  String? enqueuedTask;
  String? enqueuedRoot;
  bool closed = false;

  void _maybeFail() {
    if (failWith != null) throw failWith!;
  }

  @override
  Future<Map<String, dynamic>> health() async => {'ok': true};

  @override
  Future<Map<String, dynamic>> dirs([String? path]) async {
    _maybeFail();
    if (path == null) return dirsData;
    return listings[path] ??
        {
          'path': path,
          'parent': null,
          'roots': dirsData['roots'],
          'dirs': [
            {'name': 'src', 'path': '$path/src'}
          ],
        };
  }

  @override
  Future<Map<String, dynamic>> workspaces() async {
    _maybeFail();
    return workspacesData;
  }

  @override
  Future<Map<String, dynamic>> startWorkspace(String root) async {
    _maybeFail();
    started.add(root);
    return {
      'k': 'workspace_started',
      'workspace': {'path': root, 'state': 'running'},
    };
  }

  @override
  Future<Map<String, dynamic>> snapshot([String? root]) async {
    _maybeFail();
    if (failedRoot != null && failedRoot == root) {
      throw const LoopApiException(ApiFailure.network, 'snapshot failed');
    }
    snapshots++;
    snapshotRoots.add(root);
    return snapshotData;
  }

  @override
  Future<Map<String, dynamic>> enqueue(String task, String root) async {
    _maybeFail();
    enqueuedTask = task;
    enqueuedRoot = root;
    return {
      'k': 'queued',
      'item': {'id': 'q000001', 'task': task, 'root': root}
    };
  }

  @override
  Future<Map<String, dynamic>> runLog(String runId) async {
    _maybeFail();
    logs++;
    return logData;
  }

  @override
  void close() {
    closed = true;
  }
}
