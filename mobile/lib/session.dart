/// Last successful connection, persisted on the device for auto-login.
library;

import 'package:shared_preferences/shared_preferences.dart';

import 'models.dart';

class Session {
  static const _host = 'loop.host';
  static const _port = 'loop.port';
  static const _token = 'loop.token';

  static Future<ConnectionSettings?> load() async {
    final prefs = await SharedPreferences.getInstance();
    final host = prefs.getString(_host);
    final token = prefs.getString(_token);
    final port = prefs.getInt(_port);
    if (host == null || host.isEmpty || token == null || token.isEmpty || port == null) {
      return null;
    }
    return ConnectionSettings(host: host, port: port, token: token);
  }

  static Future<void> save(ConnectionSettings settings) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_host, settings.host);
    await prefs.setInt(_port, settings.port);
    await prefs.setString(_token, settings.token);
  }

  static Future<void> clear() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_host);
    await prefs.remove(_port);
    await prefs.remove(_token);
  }
}
