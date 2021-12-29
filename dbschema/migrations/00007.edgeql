CREATE MIGRATION m1jzxqpz4kl42wivucmlox2dlcl3zn3kn2yntavqgrv4pudodk7msa
    ONTO m1ktjlzmgqaf4errf2ab4lxext37xxgouuaokivj43s6nq7vtdoyhq
{
  ALTER TYPE default::Guild {
      CREATE SINGLE LINK log_channel -> default::GuildChannel;
  };
  ALTER TYPE default::GuildChannel {
      CREATE REQUIRED PROPERTY channel_guild_id := (.guild.guild_id);
  };
};
