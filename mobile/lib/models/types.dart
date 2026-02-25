class EventModel {
  EventModel({
    required this.id,
    required this.name,
    required this.country,
    required this.startAt,
  });

  final String id;
  final String name;
  final String country;
  final DateTime startAt;

  factory EventModel.fromJson(Map<String, dynamic> json) {
    return EventModel(
      id: json['id'] as String,
      name: json['name'] as String,
      country: json['country'] as String,
      startAt: DateTime.parse(json['start_at'] as String),
    );
  }
}

class LeaderboardRowModel {
  LeaderboardRowModel({
    required this.rank,
    required this.username,
    required this.totalPoints,
  });

  final int rank;
  final String username;
  final double totalPoints;

  factory LeaderboardRowModel.fromJson(Map<String, dynamic> json) {
    return LeaderboardRowModel(
      rank: json['rank'] as int,
      username: json['username'] as String,
      totalPoints: (json['total_points'] as num).toDouble(),
    );
  }
}
