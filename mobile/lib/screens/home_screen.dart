import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../models/types.dart';
import '../services/api_client.dart';

final upcomingEventsProvider = FutureProvider<List<EventModel>>((ref) async {
  return ref.watch(apiClientProvider).events();
});

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final eventsAsync = ref.watch(upcomingEventsProvider);

    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Apex Predict', style: Theme.of(context).textTheme.headlineMedium),
            const SizedBox(height: 8),
            Text('Upcoming race weekends', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 16),
            Expanded(
              child: eventsAsync.when(
                data: (events) {
                  if (events.isEmpty) {
                    return const Center(child: Text('No events available yet.'));
                  }
                  return ListView.builder(
                    itemCount: events.length,
                    itemBuilder: (context, index) {
                      final event = events[index];
                      return Card(
                        child: ListTile(
                          title: Text(event.name),
                          subtitle: Text(event.country),
                          trailing: Text(DateFormat('MMM d, HH:mm').format(event.startAt.toLocal())),
                        ),
                      );
                    },
                  );
                },
                loading: () => const Center(child: CircularProgressIndicator()),
                error: (error, _) => Center(child: Text('Could not load events: $error')),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
