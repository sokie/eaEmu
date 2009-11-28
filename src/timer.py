from twisted.application.internet import TimerService
from twisted.internet import task
from twisted.internet import defer


class LoopingCall(task.LoopingCall):
   def __call__(self):
      def cb(result):
         if self.running:
            self._reschedule()
         else:
            d, self.deferred = self.deferred, None
            d.callback(self)

      def eb(failure):
         self.running = False
         d, self.deferred = self.deferred, None
         d.errback(failure)

      ## HACK: bug -- reactor.callLater()
      ## seems to ignore .cancel() requests, so this
      ## method ends up getting called after the loop
      ## has been stopped.
      if self.running:
         self.call = None
         d = defer.maybeDeferred(self.f, *self.a, **self.kw)
         d.addCallbacks(cb, eb)

class KeepaliveService(TimerService):
   def __init__(self, pingFunc, step, onTimeout):
      self.step = step
      self.call = (pingFunc, [], {}) # need args to pingFunc?
      self.onTimeout = onTimeout
      self.ping = defer.Deferred()

   def alive(self):
      if not self.ping.called:
         self.ping.callback(None)

   def startService(self):
      ## this implementation of startService overrides the original

      if self.running:
         return

      pingFunc, args, kwargs = self.call

      def sendPing():
         self.ping = defer.Deferred()
         ## the pingFunc is assumed to be a syncronous function that
         ## sends the request along to the client and returns immediately.
         ## TODO: maybe assume that this returns a deferred that is fired when
         ## the response is received?
         pingFunc(*args, **kwargs)
         self.ping.setTimeout(self.step+5, self.onTimeout)
         return self.ping

      self._loop = LoopingCall(sendPing)
      self._loop.start(self.step, now=True).addErrback(self._failed)

   def stopService(self):
      ## bug in TimerService if you stop when hasnt yet started...
      ## because of condition "not hasattr(self, '_loop')"
      if self.running:
         return TimerService.stopService(self)