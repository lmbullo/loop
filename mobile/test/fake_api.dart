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
  Future<Map<String, dynamic>> snapshot() async {
    _maybeFail();
    snapshots++;
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
