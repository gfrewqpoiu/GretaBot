CREATE MIGRATION m1wqsygnsntchjly2jrw7exzos54p23x5qy5hgcw233r6wdjee3m5q
    ONTO m1g375hf7gkdrwmjyjm5gtnjgtkqik2xnotfxvnefja67ebqy4z7ka
{
  CREATE SCALAR TYPE default::discord_tag EXTENDING std::str {
      CREATE CONSTRAINT std::regexp('^#[0-9]{4}$');
  };
};
